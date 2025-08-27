from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
import requests # Import requests for the Ollama call

app = FastAPI()

# --- Embedding function (Ollama) ---
def get_embedding(text: str):
    """
    Function to get embeddings from the Ollama service.
    This must match the function used in index.py for consistency.
    """
    try:
        res = requests.post(
            "http://localhost:11434/api/embeddings",
            json={
                "model": "nomic-embed-text",  # make sure this model is pulled in Ollama
                "prompt": text
            }
        )
        res.raise_for_status()
        data = res.json()
        return data.get("embedding")
    except Exception as e:
        print(f"⚠️ Embedding failed for text: {text[:50]}... Error: {e}")
        return None

# Use PersistentClient everywhere for consistency
client = chromadb.PersistentClient(path="./chroma_db")

try:
    # We remove the embedding_function parameter here.
    # The collection was already created with a default, and we manually manage embeddings.
    collection = client.get_or_create_collection("pdf_chunks")
except Exception:
    # Same here, no embedding_function is needed.
    collection = client.get_or_create_collection("pdf_chunks")

class QueryRequest(BaseModel):
    query: str

@app.post("/query")
def query_pdf(req: QueryRequest):
    print("\n--- Incoming Query ---")
    print("Query:", req.query)

    # First, get the embedding for the user's query using the same Ollama function
    query_embedding = get_embedding(req.query)
    
    if query_embedding is None:
        return {"error": "Failed to get embedding for query."}, 500

    # Now, query the collection using the embedding vector directly.
    # This ensures the dimension is correct.
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1
    )

    print("\n--- Chroma Results ---")
    print(results)

    return {
    "results": [
    {
        "text": results["documents"][0][i],
        "images": (
            [img.strip() for img in results["metadatas"][0][i].get("images", "").split(",")]
            if results["metadatas"][0][i].get("images")
            else []
        )
    }
    for i in range(len(results["documents"][0]))
]

}


@app.get("/debug")
def debug():
    count = collection.count()
    peek = collection.peek()
    print(f"\n--- Debug ---\nCount: {count}\nSample: {peek}")
    return {
        "count": count,
        "sample": peek
    }
