import time 
import os
import pandas as pd
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import chromadb
import json

load_dotenv()

def get_chroma_collection():
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="academic_insights")
    return collection

def ingest_data_to_vector_db(file_id, df):
    collection = get_chroma_collection()
    
    # Using the exact model from your available list
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001", 
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    documents = []
    metadatas = []
    ids = []
    
    for index, row in df.iterrows():
        row_dict = {str(k): str(v) for k, v in row.items() if pd.notna(v) and v != ""}
        seat = row_dict.get("SEAT NO", "Unknown")
        name = row_dict.get("Name", "Unknown")
        
        chunk_text = (
            f"Record for {name} ({seat}). "
            f"Data: {json.dumps(row_dict)}"
        )
        
        documents.append(chunk_text)
        metadatas.append({"file_id": file_id, "type": "full_record", "seat": seat})
        ids.append(f"{file_id}_{seat}")

    print(f"Starting ingestion. This uses 768-dimension vectors...")
    
    batch_size = 2
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i : i + batch_size]
        if batch_docs:
            try:
                # This call handles both embedding and storage
                collection.add(
                    documents=batch_docs,
                    metadatas=metadatas[i : i + batch_size],
                    ids=ids[i : i + batch_size],
                    # Pass embeddings explicitly to ensure Chroma doesn't use its 384-dim default
                    embeddings=embeddings.embed_documents(batch_docs)
                )
                print(f"✅ Indexed records {i+1} to {i+len(batch_docs)}")
                time.sleep(4) 
                
            except Exception as e:
                print(f"⚠️ Error: {e}. Pausing...")
                time.sleep(10)
    
    print(f"🏁 Finished ingestion for {file_id}")
    return True