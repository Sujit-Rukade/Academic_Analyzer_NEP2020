import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
import chromadb
import ast

load_dotenv()

@tool
def search_academic_insights(query: str, file_id: str) -> str:
    """Use this tool to search the vector database for student marks, SGPAs, and subject performance."""
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="academic_insights")
    
    # MUST match the model used in rag_ingest.py
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    query_embedding = embeddings.embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5, 
        where={"file_id": file_id}
    )
    
    if not results['documents'] or not results['documents'][0]:
        return "No specific data found for this query."
    
    return "\n".join(results['documents'][0])

def ask_rag_agent(question: str, file_id: str) -> str:
    llm = ChatGoogleGenerativeAI(
        # model="models/gemini-3.1-flash-lite-preview", 
        model="models/gemini-3.1-flash-lite-preview", 
        # model="models/gemini-2.5-flash", 
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Assuming you are using the search_academic_insights tool
    tools = [search_academic_insights] 
    agent = create_react_agent(llm, tools)
    
    system_prompt = (
        f"You are the Academic Advisor for PICT. You are analyzing the result file: {file_id}. "
        "Use the search_academic_insights tool to find specific student details. "
        "Read the returned JSON data carefully to answer questions. "
        "If the tool returns no data, tell the user you don't have that information. "
        
        # --- NEW RULES TO STOP HALLUCINATION ---
        "CRITICAL DATA RULES: "
        "1. Do NOT invent grades or guess missing values. "
        "2. NEVER calculate the SGPA, Totals, or Credits yourself. "
        "3. If a specific metric like SGPA is NOT explicitly written in the retrieved JSON data, output 'N/A (Backlog)' or 'Not Provided'. "
        
        # --- NEW FORMATTING INSTRUCTIONS ---
        "CRITICAL FORMATTING RULES: "
        "1. Never output a raw block of text. "
        "2. Use Markdown headings (###) to separate sections (e.g., ### Student Profile, ### Subject Performance). "
        "3. Present grades and marks using bullet points or Markdown tables for easy scanning. "
        "4. Bold key metrics like SGPA, total marks, and final grades. "
        "5. Provide a short, clearly separated 'Insights & Recommendations' section at the end. "
        "Make the output look like a professional, clean academic report card."
    )
    
    # ... previous code ...
    inputs = {"messages": [("system", system_prompt), ("user", question)]}
    response = agent.invoke(inputs)
    
    raw_content = response["messages"][-1].content
    
    # THE FIX: Forcibly extract the text, ignoring signatures and metadata
    
    # Scenario 1: LangChain returned a stringified list (This is what is happening to you)
    if isinstance(raw_content, str) and raw_content.strip().startswith("[{"):
        try:
            parsed_list = ast.literal_eval(raw_content)
            clean_text = ""
            for item in parsed_list:
                if isinstance(item, dict) and "text" in item:
                    clean_text += item["text"]
            return clean_text
        except Exception:
            pass # Fallback if parsing fails

    # Scenario 2: LangChain returned an actual Python list
    if isinstance(raw_content, list):
        clean_text = ""
        for item in raw_content:
            if isinstance(item, dict) and "text" in item:
                clean_text += item.get("text", "")
            elif isinstance(item, str):
                clean_text += item
        return clean_text
        
    # Scenario 3: It's a normal string
    return raw_content





# import os
# import json
# import re
# import ast
# import chromadb
# import pandas as pd
# from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# from langchain_core.tools import tool
# from langgraph.prebuilt import create_react_agent

# load_dotenv()

# # --- PRIVACY LAYER GLOBALS ---
# # These act as temporary memory to swap real data with fake tokens and back again
# CURRENT_REVERSE_MAP = {}
# STUDENT_NAMES_LIST = []
# MASK_COUNTER = 1

# def apply_privacy_mask(text: str) -> str:
#     """Hides Names, Seat Nos, and PRNs from the text before sending to LLM."""
#     global CURRENT_REVERSE_MAP, STUDENT_NAMES_LIST, MASK_COUNTER
#     safe_text = text
    
#     # 1. Mask Seat Numbers (Pattern: S followed by 9 digits)
#     seat_matches = set(re.findall(r'[S]\d{9}', safe_text))
#     for seat in seat_matches:
#         token = f"[SEAT_NO_{MASK_COUNTER}]"
#         CURRENT_REVERSE_MAP[token] = seat
#         safe_text = safe_text.replace(seat, token)
#         MASK_COUNTER += 1

#     # 2. Mask PRNs (Pattern: F + 2 digits + 2 letters + 3 digits)
#     prn_matches = set(re.findall(r'[F]\d{2}[A-Z]{2}\d{3}', safe_text))
#     for prn in prn_matches:
#         token = f"[PRN_{MASK_COUNTER}]"
#         CURRENT_REVERSE_MAP[token] = prn
#         safe_text = safe_text.replace(prn, token)
#         MASK_COUNTER += 1

#     # 3. Mask Actual Student Names (Dynamically from the uploaded PDF)
#     for name in STUDENT_NAMES_LIST:
#         if pd.notna(name) and str(name).strip() != "" and str(name) in safe_text:
#             token = f"[STUDENT_NAME_{MASK_COUNTER}]"
#             CURRENT_REVERSE_MAP[token] = str(name)
#             safe_text = safe_text.replace(str(name), token)
#             MASK_COUNTER += 1
            
#     return safe_text

# def remove_privacy_mask(llm_response: str) -> str:
#     """Restores the real Names, Seat Nos, and PRNs before showing to the user."""
#     global CURRENT_REVERSE_MAP
#     final_text = llm_response
#     for token, real_value in CURRENT_REVERSE_MAP.items():
#         final_text = final_text.replace(token, real_value)
#     return final_text

# # --- TOOL 1: INDIVIDUAL SEARCH ---
# @tool
# def search_student_details(query: str, file_id: str) -> str:
#     """Use this to find specific marks, grades, or details about an individual student."""
#     client = chromadb.PersistentClient(path="./chroma_db")
#     collection = client.get_or_create_collection(name="academic_insights")
#     embeddings = GoogleGenerativeAIEmbeddings(
#         model="models/gemini-embedding-001",
#         google_api_key=os.getenv("GOOGLE_API_KEY")
#     )
    
#     results = collection.query(
#         query_embeddings=[embeddings.embed_query(query)],
#         n_results=5, 
#         where={"file_id": file_id}
#     )
    
#     if not results['documents'] or not results['documents'][0]:
#         return "No student found."
        
#     raw_data = "\n".join(results['documents'][0])
    
#     # SECURITY: Mask the data before returning it to the LLM's brain!
#     return apply_privacy_mask(raw_data)

# # --- TOOL 2: AGGREGATE STATS ---
# @tool
# def get_subject_backlog_stats() -> str:
#     """Use this to answer questions about subject trends or class-wide statistics."""
#     try:
#         with open('subject_backlogs.json', 'r') as f:
#             data = json.load(f)
#         return json.dumps(data)
#     except:
#         return "Subject backlog data not available yet."

# # --- MAIN AGENT CALL ---
# # Notice we added 'df' as a parameter so we know all the names in the current class
# def ask_rag_agent(question: str, file_id: str, df: pd.DataFrame = None) -> str:
#     global CURRENT_REVERSE_MAP, STUDENT_NAMES_LIST, MASK_COUNTER
    
#     # Reset the privacy map for every new question
#     CURRENT_REVERSE_MAP = {}
#     MASK_COUNTER = 1
    
#     # Load the names from the dataframe if provided
#     if df is not None and "Name" in df.columns:
#         STUDENT_NAMES_LIST = df["Name"].tolist()
    
#     # FIX: Using 'latest' bypasses the 20/day limit of 2.5-flash
#     llm = ChatGoogleGenerativeAI(
#         model="models/gemini-3.1-flash-lite-preview", 
#         google_api_key=os.getenv("GOOGLE_API_KEY")
#     )
    
#     tools = [search_student_details, get_subject_backlog_stats]
#     agent = create_react_agent(llm, tools)
    
#     system_prompt = (
#         f"You are the Academic Advisor for PICT. You are analyzing the result file: {file_id}. "
#         "Use the search_student_details tool to find specific student details. "
        
#         "CRITICAL DATA RULES: "
#         "1. Do NOT invent grades or guess missing values. "
#         "2. NEVER calculate the SGPA, Totals, or Credits yourself. "
#         "3. If a specific metric like SGPA is NOT explicitly written in the retrieved data, output 'N/A (Backlog)' or 'Not Provided'. "
        
#         "CRITICAL FORMATTING RULES: "
#         "1. Never output a raw block of text. Use Markdown headings (###). "
#         "2. Present grades using bullet points or Markdown tables. "
#         "3. Bold key metrics like final grades. "
#         "4. Provide a short 'Insights & Recommendations' section."
#     )
    
#     # SECURITY: Mask the user's prompt before the LLM sees it
#     safe_question = apply_privacy_mask(question)
    
#     inputs = {"messages": [("system", system_prompt), ("user", safe_question)]}
#     # Print what the LLM is actually going to see
#     print("\n" + "="*40)
#     print("🕵️ BACKEND DEBUG: WHAT THE LLM SEES")
#     print("="*40)
#     print(f"Masked Prompt: {safe_question}")
#     print(f"Current Privacy Dictionary: {CURRENT_REVERSE_MAP}")
#     print("="*40 + "\n")
#     response = agent.invoke(inputs)
#     raw_content = response["messages"][-1].content
    
#     # FIX: The Foolproof Extraction to remove garbage signature strings
#     extracted_text = raw_content
#     if isinstance(raw_content, str) and raw_content.strip().startswith("[{"):
#         try:
#             parsed_list = ast.literal_eval(raw_content)
#             extracted_text = ""
#             for block in parsed_list:
#                 if isinstance(block, dict) and "text" in block:
#                     extracted_text += block["text"]
#         except Exception:
#             pass
#     elif isinstance(raw_content, list):
#         extracted_text = ""
#         for block in raw_content:
#             if isinstance(block, dict) and "text" in block:
#                 extracted_text += block.get("text", "")
#             elif isinstance(block, str):
#                 extracted_text += block

#     # SECURITY: Put the real names back in before showing the Streamlit UI
#     final_output = remove_privacy_mask(extracted_text)
    
#     return final_output