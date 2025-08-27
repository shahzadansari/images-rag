import chromadb
import requests
import json
from pathlib import Path

# --- Connect to Chroma ---
script_dir = Path(__file__).resolve().parent
client = chromadb.PersistentClient(path=str(script_dir / "chroma_db"))
collection = client.get_or_create_collection("pdf_chunks")


# --- Ollama embedding function ---
def get_embedding(input_text: str):
    try:
        resp = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": input_text},
        )
        resp.raise_for_status()
        data = resp.json()

        # 👀 Debug raw embedding response
        print("\n--- Raw embedding response ---")
        print(json.dumps(data, indent=2))

        return data["embedding"]
    except requests.RequestException as e:
        print(f"⚠️ HTTP error embedding query: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"⚠️ Parse error embedding query: {e}")
        return None


# --- Query function ---
def search(query: str, n_results: int = 3):
    embedding = get_embedding(query)
    if embedding is None:
        return {"results": []}

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    return results


# --- Example usage ---
if __name__ == "__main__":
    user_query = "What does the PDF say about blood donation?"
    res = search(user_query, n_results=1)

    print("\n🔍 Query Results:")
    print(json.dumps(res, indent=2))
