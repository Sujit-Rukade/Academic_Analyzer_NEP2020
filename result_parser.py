import re
import pdfplumber
import pandas as pd
import json

SUB_FIELDS = [
    "COURSE NAME", "ESE", "ATTD", "CIE", "INSEM",
    "OR", "TW", "PR", "TOTAL", "TOT %",
    "CRD", "GRD", "GP", "CP", "ORD",
]

_MARKS_START = re.compile(r"^\d+/\d+$|^---$")
_COURSE_ID = re.compile(r"^\d{6,7}$")
_PURE_NUM = re.compile(r"^\d+(\.\d+)?$")

GRADE_TOKENS = {"O", "A+", "A", "B+", "B", "C", "D", "P", "F", "FF", "Ab", "AB", "ABS"}

def _clean(token):
    return token.lstrip("*$#").rstrip("$#").strip()

def _is_name_noise(token):
    """Reject tokens that are clearly not part of a course title."""
    t = _clean(token)
    if not t:
        return True
    if _COURSE_ID.match(t):
        return True
    if _MARKS_START.match(t):
        return True
    if _PURE_NUM.match(t):
        return True
    if t in GRADE_TOKENS:
        return True
    if t.upper() in SUB_FIELDS:
        return True
    return False

def _sanitize_subject_name(raw_name):
    """Remove known PDF artifacts that can leak into course names."""
    if not raw_name:
        return raw_name

    cleaned = re.sub(r"\s+", " ", raw_name).strip(" :,-")

    # Drop leaked student header fragments like: ": S240502230 Name ..."
    cleaned = re.sub(r"^:?\s*S?\d{8,}\s+Name\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^:?\s*Name\s+", "", cleaned, flags=re.IGNORECASE)

    # Remove trailing assessment-note/footer artifacts.
    cleaned = re.sub(r"-{3,}.*$", "", cleaned).strip()
    cleaned = re.sub(r"\bCONFIDENTIAL\b.*$", "", cleaned, flags=re.IGNORECASE).strip(" ,-")
    cleaned = re.sub(
        r",?\s*CCE\s*=\s*Continuous.*$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip(" ,-")

    # Keep subject title clean; type is appended separately.
    cleaned = re.sub(
        r"\b(THEORY|PRACTICAL|ORAL|PROJECT)\b$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    return cleaned

def get_subject_type(name, total, seen):
    name_l = name.lower()
    total_clean = str(total).replace("$", "").replace("#", "")

    if "lab" in name_l:
        return "Practical"

    if any(k in name_l for k in ["practical", "oral", "project", "seminar"]):
        return "Practical"

    if "/100" in total_clean:
        return "Theory"

    # If the student takes the same subject twice (Theory row & Practical row)
    if name in seen and "/100" not in total_clean:
        return "Practical"

    return "Skill"

def should_skip_line(line):
    upper = line.upper()
    if "SGPA" in upper: return False
    if upper.startswith("COLLEGE") or "PUN CODE" in upper: return True
    if upper.startswith("PROGRAM") or "PROGRAM :" in upper: return True
    if "COURSE NAME" in upper and "ESE" in upper: return True
    if upper.startswith("SEM:") or upper.startswith("SEM :"): return True
    if upper.startswith("LEGENDS"): return True
    if "PAGE NO" in upper: return True
    if "TOTAL EARNED" in upper or ("CREDIT" in upper and "EARNED" in upper): return True
    if upper.startswith("SEAT NO") and "COURSE NAME" in upper: return True
    
    # Universal artifacts
    if "ABOUT:BLANK" in upper: return True
    if "--- PAGE" in upper: return True
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", line): return True 
    return False

def group_into_lines(words, tolerance=4.0):
    """Physically groups floating words into horizontal lines."""
    if not words: return []
    words.sort(key=lambda w: (w['top'], w['x0']))
    lines = []
    current_line = []
    current_top = None
    
    for w in words:
        if current_top is None:
            current_top = w['top']
            current_line.append(w)
        elif abs(w['top'] - current_top) <= tolerance:
            current_line.append(w)
        else:
            current_line.sort(key=lambda x: x['x0'])
            lines.append(current_line)
            current_line = [w]
            current_top = w['top']
            
    if current_line:
        current_line.sort(key=lambda x: x['x0'])
        lines.append(current_line)
    return lines

def pdf_to_excel_wide(pdf_path, excel_path,
                      student_json="student_backlogs.json",
                      subject_json="subject_backlogs.json"):

    student_records = {}
    all_courses = set()
    backlog_by_student = {}
    backlog_by_subject = {}

    seat_pattern = re.compile(
        r"SEAT\s*NO\s*:\s*(\S+).*?Name\s*:\s*(.*?)\s+Mother\s*:\s*(.*?)\s+PRN\s*:\s*(\S+)"
    )
    sgpa_pattern = re.compile(r"SGPA\s*:\s*([\d.]+|-)")

    active_seat_info = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            if not words: continue
            
            # 1. Group into lines to safely filter out headers/footers
            page_lines = group_into_lines(words)
            valid_words = []
            
            for line in page_lines:
                full_line_text = " ".join([w['text'] for w in line])
                if not should_skip_line(full_line_text):
                    valid_words.extend(line)
                    
            if not valid_words: continue
            
            # 2. Re-group valid words
            page_lines = group_into_lines(valid_words)
            
            # Find students and SGPAs to define blocks
            student_blocks = [] 
            current_seat = active_seat_info
            current_top = 0 if current_seat else None
            
            for line in page_lines:
                full_line_text = " ".join([w['text'] for w in line])
                
                m_seat = seat_pattern.search(full_line_text)
                if m_seat:
                    if current_seat:
                        # Close previous student if no SGPA was found
                        student_blocks.append({
                            'seat_info': current_seat,
                            'sgpa': "",
                            'top': current_top,
                            'bottom': line[0]['top'] - 1
                        })
                    current_seat = m_seat.groups()
                    current_top = line[0]['top']

                    active_seat_info = current_seat 
                    
                    continue
                    
                if "SGPA" in full_line_text and current_seat:
                    m_sgpa = sgpa_pattern.search(full_line_text)
                    student_blocks.append({
                        'seat_info': current_seat,
                        'sgpa': m_sgpa.group(1) if m_sgpa else "",
                        'top': current_top,
                        'bottom': line[0]['bottom'] + 1 
                    })
                    current_seat = None
                    current_top = None

                    active_seat_info = None

            if current_seat:
                student_blocks.append({
                    'seat_info': current_seat,
                    'sgpa': "",
                    'top': current_top,
                    'bottom': page.height
                })

            for s_block in student_blocks:
                seat_info = s_block['seat_info']
                sgpa = s_block.get('sgpa', '')
                
                seat, name, mother, prn = seat_info
                seat, name, mother, prn = seat.strip(), name.strip(), mother.strip(), prn.strip()
                
                if seat not in student_records:
                    student_records[seat] = {
                        "SEAT NO": seat, "Name": name, "Mother Name": mother,
                        "PRN": prn, "SGPA": sgpa, "_course_counts": {},
                        "_seen": set(), "_cache": {}
                    }
                elif sgpa:
                    student_records[seat]["SGPA"] = sgpa

                if seat not in backlog_by_student:
                    backlog_by_student[seat] = {"Name": name, "Backlogs": [], "Count": 0}

                # 3. Y-Banding: Find courses for this student
                s_words = [w for w in valid_words if s_block['top'] <= w['top'] <= s_block['bottom']]
                
                course_id_words = []
                for w in s_words:
                    clean_tok = w['text'].replace("*", "").strip()
                    # A course ID strictly sits on the far left of the page (x0 < 80)
                    if w['x0'] < 80 and re.match(r"^\d{6,7}$", clean_tok):
                        course_id_words.append(w)
                
                course_id_words.sort(key=lambda w: w['top'])
                
                if not course_id_words: continue
                
                # Assign precise vertical boundaries for each course to prevent wrapped text crossing over
                for i, cid_w in enumerate(course_id_words):
                    c_id = cid_w['text'].replace("*", "").strip()
                    
                    if i == 0:
                        # Start first course close to its own row, not from student header block.
                        top_bound = cid_w['top'] - 2.0
                    else:
                        top_bound = (course_id_words[i-1]['top'] + cid_w['top']) / 2.0
                        
                    if i == len(course_id_words) - 1:
                        bottom_bound = s_block['bottom']
                    else:
                        bottom_bound = (cid_w['top'] + course_id_words[i+1]['top']) / 2.0
                        
                    # Filter only words belonging to this precise geometric course bucket
                    c_words = [w for w in s_words if top_bound <= w['top'] < bottom_bound]
                    c_lines = group_into_lines(c_words)
                    
                    names = []
                    marks = []
                    
                    for line in c_lines:
                        in_marks = False
                        for w in line:
                            clean_tok = w['text'].replace("$", "").replace("#", "").replace("*", "").strip()
                            if not clean_tok: continue 
                            
                            # Skip the course ID itself
                            if w['x0'] < 80 and _COURSE_ID.match(clean_tok):
                                continue

                            is_frac_or_dash = bool(_MARKS_START.match(clean_tok))
                            is_grade = clean_tok in GRADE_TOKENS
                            is_num = bool(_PURE_NUM.match(clean_tok))

                            if not in_marks:
                                # Marks region starts with fractions, or right-side grade/number tokens.
                                if is_frac_or_dash or ((is_grade or is_num) and w['x0'] > 220):
                                    in_marks = True
                                    marks.append(w['text'])
                                else:
                                    # Accept subject-name tokens strictly from the subject-name column.
                                    if 80 <= w['x0'] <= 230 and not _is_name_noise(clean_tok):
                                        names.append(w['text'])
                            else:
                                marks.append(w['text'])

                    # Assemble perfect names
                    raw_name = " ".join([_clean(t) for t in names if _clean(t)])
                    raw_name = _sanitize_subject_name(raw_name)

                    cache = student_records[seat]["_cache"]
                    if raw_name:
                        cache[c_id] = raw_name
                    elif c_id in cache:
                        raw_name = cache[c_id]
                    else:
                        raw_name = f"COURSE_{c_id}"

                    rest = [t.replace("$", "").replace("#", "") for t in marks]
                    while len(rest) < 14:
                        rest.append("---")
                    
                    ese, attd, cie, insem, or_, tw, pr, total, tot, crd, grd, gp, cp, ord_ = rest[:14]

                    # Uniform Tagging
                    seen = student_records[seat]["_seen"]
                    typ = get_subject_type(raw_name, total, seen)
                    seen.add(raw_name)

                    tagged = f"{raw_name} ({typ})"

                    if tagged not in backlog_by_subject:
                        backlog_by_subject[tagged] = {"Count": 0, "Students": []}

                    # Manage repetitive courses
                    counts = student_records[seat]["_course_counts"]
                    key = f"{c_id}_{tagged}"
                    counts[key] = counts.get(key, 0) + 1
                    
                    suffix = chr(96 + counts[key])
                    prefix = f"{c_id}{suffix}"
                    all_courses.add(prefix)

                    # Apply to record
                    rec = student_records[seat]
                    rec[f"{prefix}_COURSE NAME"] = tagged
                    rec[f"{prefix}_ESE"] = ese
                    rec[f"{prefix}_ATTD"] = attd
                    rec[f"{prefix}_CIE"] = cie
                    rec[f"{prefix}_INSEM"] = insem
                    rec[f"{prefix}_OR"] = or_
                    rec[f"{prefix}_TW"] = tw
                    rec[f"{prefix}_PR"] = pr
                    rec[f"{prefix}_TOTAL"] = total
                    rec[f"{prefix}_TOT %"] = tot
                    rec[f"{prefix}_CRD"] = crd
                    rec[f"{prefix}_GRD"] = grd
                    rec[f"{prefix}_GP"] = gp
                    rec[f"{prefix}_CP"] = cp
                    rec[f"{prefix}_ORD"] = ord_

                    # -------- BACKLOG --------
                    if grd in ["F", "FF"]:
                        bs = backlog_by_student[seat]
                        if tagged not in bs["Backlogs"]:
                            bs["Backlogs"].append(tagged)
                            bs["Count"] += 1

                        # --- 2. YOU CAN LEAVE THIS AS IS (It's now safely redundant) ---
                        if tagged not in backlog_by_subject:
                            backlog_by_subject[tagged] = {"Count": 0, "Students": []}

                        if bs["Name"] not in backlog_by_subject[tagged]["Students"]:
                            backlog_by_subject[tagged]["Students"].append(bs["Name"])
                            backlog_by_subject[tagged]["Count"] += 1

    # ---------------- DATAFRAME COMPILATION ----------------
    student_cols = ["SEAT NO", "Name", "Mother Name", "PRN", "SGPA"]
    course_cols = []

    for c in sorted(all_courses):
        for f in SUB_FIELDS:
            course_cols.append(f"{c}_{f}")

    df = pd.DataFrame.from_dict(student_records, orient="index")
    if not df.empty:
        df = df.drop(columns=[c for c in ["_course_counts", "_seen", "_cache"] if c in df.columns])

        for col in student_cols + course_cols:
            if col not in df.columns:
                df[col] = ""

        df = df[student_cols + course_cols].reset_index(drop=True)
        df.to_excel(excel_path, index=False)
    else:
        print("No student records found!")

    with open(student_json, "w", encoding="utf-8") as f:
        json.dump(backlog_by_student, f, indent=2, ensure_ascii=False)

    with open(subject_json, "w", encoding="utf-8") as f:
        json.dump(backlog_by_subject, f, indent=2, ensure_ascii=False)

    print(f"✅ Excel output formatted to: {excel_path}")

if __name__ == "__main__":
    pdf_to_excel_wide(
        "S.Y.B.Tech - ETE - 5 - ConsolidateGazette.pdf", # Change this to your exact path
        "output_wide.xlsx"
    )