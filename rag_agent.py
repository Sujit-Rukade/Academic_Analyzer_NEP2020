import ast
import os
import re

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from rag_ingest import (
    build_metrics_summary_text,
    build_student_summary_text,
    build_subject_summary_text,
    get_chroma_collection,
    get_embeddings,
)

load_dotenv()

_COURSE_QUESTION = re.compile(
    r"\b(course|courses|subject|subjects|paper|papers)\b", re.IGNORECASE
)
_STUDENT_QUESTION = re.compile(
    r"\b(student|students|learner|learners|classmate|classmates)\b", re.IGNORECASE
)
_RANK_QUESTION = re.compile(
    r"\b(top|rank|ranks|ranking|leaderboard|topper|toppers|highest|best|first)\b", re.IGNORECASE
)


def is_rag_configured() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY"))


def _extract_response_text(raw_content):
    if isinstance(raw_content, str) and raw_content.strip().startswith("[{"):
        try:
            parsed_list = ast.literal_eval(raw_content)
            clean_text = ""
            for item in parsed_list:
                if isinstance(item, dict) and "text" in item:
                    clean_text += item["text"]
            return clean_text
        except Exception:
            pass

    if isinstance(raw_content, list):
        clean_text = ""
        for item in raw_content:
            if isinstance(item, dict) and "text" in item:
                clean_text += item.get("text", "")
            elif isinstance(item, str):
                clean_text += item
        return clean_text

    return raw_content


def _build_authoritative_context(conversion):
    if not conversion:
        return "No structured summary available."

    sections = [
        "=== AUTHORITATIVE COURSE/SUBJECT BACKLOG DATA ===",
        build_subject_summary_text(conversion.get("subjectBacklogData")),
        "",
        "=== AUTHORITATIVE STUDENT BACKLOG DATA ===",
        build_student_summary_text(conversion.get("studentBacklogData")),
        "",
        "=== AUTHORITATIVE CLASS METRICS ===",
        build_metrics_summary_text(
            conversion.get("metrics"),
            conversion.get("top3"),
        ),
    ]
    return "\n".join(sections)


def _retrieve_context(question: str, file_id: str):
    collection = get_chroma_collection()
    embeddings = get_embeddings()
    query_embedding = embeddings.embed_query(question)

    chunks = []
    seen = set()

    def add_results(results):
        if not results.get("documents") or not results["documents"][0]:
            return
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            doc_id = f"{meta.get('type')}::{doc[:80]}"
            if doc_id not in seen:
                seen.add(doc_id)
                chunks.append(doc)

    general = collection.query(
        query_embeddings=[query_embedding],
        n_results=5,
        where={"file_id": file_id},
    )
    add_results(general)

    asks_about_courses = bool(_COURSE_QUESTION.search(question))
    asks_about_students = bool(_STUDENT_QUESTION.search(question))

    if asks_about_courses and not asks_about_students:
        subject_results = collection.get(
            where={"$and": [{"file_id": file_id}, {"type": "subject_summary"}]}
        )
        if subject_results.get("documents"):
            for doc in subject_results["documents"]:
                doc_id = f"subject_summary::{doc[:80]}"
                if doc_id not in seen:
                    seen.add(doc_id)
                    chunks.insert(0, doc)

    if asks_about_students and not asks_about_courses:
        student_results = collection.get(
            where={"$and": [{"file_id": file_id}, {"type": "student_summary"}]}
        )
        if student_results.get("documents"):
            for doc in student_results["documents"]:
                doc_id = f"student_summary::{doc[:80]}"
                if doc_id not in seen:
                    seen.add(doc_id)
                    chunks.insert(0, doc)

    asks_about_ranks = bool(_RANK_QUESTION.search(question))
    if asks_about_ranks:
        rank_results = collection.get(
            where={"$and": [{"file_id": file_id}, {"type": "metrics_summary"}]}
        )
        if rank_results.get("documents"):
            for doc in rank_results["documents"]:
                doc_id = f"metrics_summary::{doc[:80]}"
                if doc_id not in seen:
                    seen.add(doc_id)
                    chunks.insert(0, doc)

    if not chunks:
        return "No specific data found for this query."
    return "\n\n".join(chunks)


def ask_rag_agent(question: str, file_id: str, conversion=None) -> str:
    if not is_rag_configured():
        raise RuntimeError("GOOGLE_API_KEY is not configured.")

    authoritative_context = _build_authoritative_context(conversion)
    retrieved_context = _retrieve_context(question, file_id)

    llm = ChatGoogleGenerativeAI(
        model="models/gemini-3.1-flash-lite-preview",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        max_retries=1,
    )

    system_prompt = f"""
    You are the Academic Advisor for PICT. You are analyzing the result file: {file_id}.

    Use the AUTHORITATIVE summaries first for backlog, course, subject, and class-wide questions.
    Use retrieved student records only for individual grade or mark lookups.

    <authoritative_data>
    {authoritative_context}
    </authoritative_data>

    <retrieved_data>
    {retrieved_context}
    </retrieved_data>

    User Question: {question}

    CRITICAL INTERPRETATION RULES:
    1. "courses/subjects with zero backlogs" means courses where NO student has a backlog.
       Answer with course/subject names from the COURSE/SUBJECT BACKLOG DATA only.
    2. "students with zero backlogs" means students who have no backlog in any course.
       Answer with student names from the STUDENT BACKLOG DATA only.
    3. Never answer a course/subject question with a student list.
    4. Never answer a student question with a course list unless the user explicitly asks which courses those students failed.

    CRITICAL DATA RULES:
    1. Do NOT invent grades or guess missing values.
    2. NEVER calculate the SGPA, Totals, or Credits yourself.
    3. If a specific metric like SGPA is NOT explicitly written in the data, output 'N/A (Backlog)' or 'Not Provided'.

    CRITICAL FORMATTING RULES:
    1. Never output a raw block of text.
    2. Use Markdown headings (###) to separate sections.
    3. Present grades and marks using bullet points or Markdown tables.
    4. Bold key metrics like SGPA, total marks, and final grades.
    5. Provide a short 'Insights & Recommendations' section at the end.
    """

    response = llm.invoke(system_prompt)
    return _extract_response_text(response.content)
