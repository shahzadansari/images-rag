from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import chromadb
import requests  # Import requests for the Ollama call
from pathlib import Path

app = FastAPI()


# --- Embedding function (Ollama) ---
def get_embedding(input_text: str):
    """
    Function to get embeddings from the Ollama service.
    This must match the function used in index.py for consistency.
    """
    try:
        res = requests.post(
            "http://localhost:11434/api/embeddings",
            json={
                "model": "nomic-embed-text",  # make sure this model is pulled in Ollama
                "prompt": input_text,
            },
        )
        res.raise_for_status()
        data = res.json()
        return data.get("embedding")
    except requests.RequestException as e:
        print(f"⚠️ Embedding HTTP error for text: {input_text[:50]}... Error: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"⚠️ Embedding parse error for text: {input_text[:50]}... Error: {e}")
        return None


# Use PersistentClient everywhere for consistency
script_dir = Path(__file__).resolve().parent
client = chromadb.PersistentClient(path=str(script_dir / "chroma_db"))

try:
    # We remove the embedding_function parameter here.
    # The collection was already created with a default, and we manually manage embeddings.
    collection = client.get_or_create_collection("pdf_chunks")
except Exception:
    # Same here, no embedding_function is needed.
    collection = client.get_or_create_collection("pdf_chunks")


class QueryRequest(BaseModel):
    query: str


# Serve images directory statically for the UI
images_dir = script_dir / "images"
images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")


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
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    print("\n--- Chroma Results ---")
    print(results)

    shaped = []
    for i in range(len(results.get("documents", [[" "]])[0])):
        doc_text = results["documents"][0][i]
        md = results["metadatas"][0][i] if results.get("metadatas") else {}
        img_field = (md.get("images") or "").strip()
        imgs = [p.strip() for p in img_field.split(",") if p.strip()]
        shaped.append(
            {
                "text": doc_text,
                "images": imgs,
                "page": md.get("page"),
                "bbox": md.get("bbox"),
                "distance": (results.get("distances") or [[None]])[0][i],
            }
        )

    return {"results": shaped}


@app.get("/debug")
def debug():
    count = collection.count()
    peek = collection.peek()
    print(f"\n--- Debug ---\nCount: {count}\nSample: {peek}")
    return {"count": count, "sample": peek}
