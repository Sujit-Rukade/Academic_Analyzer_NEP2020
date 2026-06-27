import json
import os

import chromadb
import pandas as pd
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "academic_insights"

_chroma_client = None
_chroma_collection = None
_embeddings = None


def get_chroma_collection():
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_collection = _chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    return _chroma_collection


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings


def is_file_indexed(file_id: str) -> bool:
    collection = get_chroma_collection()
    results = collection.get(where={"file_id": file_id}, limit=1)
    return bool(results.get("ids"))


def delete_file_from_index(file_id: str) -> None:
    collection = get_chroma_collection()
    existing = collection.get(where={"file_id": file_id})
    if existing.get("ids"):
        collection.delete(ids=existing["ids"])


def build_subject_summary_text(subject_backlog_data):
    if not subject_backlog_data:
        return "No course backlog data available."

    zero_backlog_courses = []
    courses_with_backlogs = []

    for course, info in subject_backlog_data.items():
        count = info.get("Count", 0)
        if count == 0:
            zero_backlog_courses.append(course)
        else:
            students = info.get("Students", [])
            courses_with_backlogs.append(
                f"- {course}: {count} backlog(s) — students: {', '.join(students)}"
            )

    lines = [
        "Course and subject backlog summary for this result file.",
        f"Total courses tracked: {len(subject_backlog_data)}.",
        f"Courses with ZERO backlogs ({len(zero_backlog_courses)}): "
        f"{', '.join(sorted(zero_backlog_courses)) if zero_backlog_courses else 'None'}.",
        f"Courses WITH backlogs ({len(courses_with_backlogs)}):",
    ]
    lines.extend(sorted(courses_with_backlogs))
    return "\n".join(lines)


def build_student_summary_text(student_backlog_data):
    if not student_backlog_data:
        return "No student backlog data available."

    zero_backlog_students = []
    students_with_backlogs = []

    for seat, info in student_backlog_data.items():
        name = info.get("Name", "Unknown")
        count = info.get("Count", 0)
        if count == 0:
            zero_backlog_students.append(f"{name} ({seat})")
        else:
            backlogs = ", ".join(info.get("Backlogs", []))
            students_with_backlogs.append(
                f"- {name} ({seat}): {count} backlog(s) — {backlogs}"
            )

    lines = [
        "Student backlog summary for this result file.",
        f"Total students tracked: {len(student_backlog_data)}.",
        f"Students with ZERO backlogs ({len(zero_backlog_students)}): "
        f"{', '.join(zero_backlog_students) if zero_backlog_students else 'None'}.",
        f"Students WITH backlogs ({len(students_with_backlogs)}):",
    ]
    lines.extend(sorted(students_with_backlogs))
    return "\n".join(lines)


def build_metrics_summary_text(metrics=None, top3=None):
    lines = ["Class-wide metrics summary for this result file."]
    if metrics:
        lines.extend(
            [
                f"Total students: {metrics.get('totalStudents', 'N/A')}.",
                f"Courses found: {metrics.get('coursesFound', 'N/A')}.",
                f"Total backlogs: {metrics.get('totalBacklogs', 'N/A')}.",
                f"Students with backlogs: {metrics.get('studentsWithBacklogs', 'N/A')}.",
            ]
        )
    if top3:
        lines.append("Top students by SGPA:")
        for row in top3:
            lines.append(
                f"- Rank {row.get('Rank')}: {row.get('Name')} "
                f"(Seat {row.get('SEAT NO')}, SGPA {row.get('SGPA')})"
            )
    return "\n".join(lines)


def ingest_data_to_vector_db(
    file_id,
    df,
    student_backlog_data=None,
    subject_backlog_data=None,
    metrics=None,
    top3=None,
):
    collection = get_chroma_collection()
    embeddings = get_embeddings()

    delete_file_from_index(file_id)

    documents = []
    metadatas = []
    ids = []

    summary_chunks = [
        (
            f"{file_id}_summary_subjects",
            build_subject_summary_text(subject_backlog_data),
            {"file_id": file_id, "type": "subject_summary", "seat": "summary"},
        ),
        (
            f"{file_id}_summary_students",
            build_student_summary_text(student_backlog_data),
            {"file_id": file_id, "type": "student_summary", "seat": "summary"},
        ),
        (
            f"{file_id}_summary_metrics",
            build_metrics_summary_text(metrics, top3),
            {"file_id": file_id, "type": "metrics_summary", "seat": "summary"},
        ),
    ]

    for chunk_id, text, metadata in summary_chunks:
        documents.append(text)
        metadatas.append(metadata)
        ids.append(chunk_id)

    for _, row in df.iterrows():
        row_dict = {str(k): str(v) for k, v in row.items() if pd.notna(v) and v != ""}
        seat = row_dict.get("SEAT NO", "Unknown")
        name = row_dict.get("Name", "Unknown")

        chunk_text = (
            f"Individual student record for {name} ({seat}). "
            f"Grades and marks: {json.dumps(row_dict)}"
        )

        documents.append(chunk_text)
        metadatas.append({"file_id": file_id, "type": "student_record", "seat": seat})
        ids.append(f"{file_id}_{seat}")

    if not documents:
        return False

    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
        embeddings=embeddings.embed_documents(documents),
    )
    return True
