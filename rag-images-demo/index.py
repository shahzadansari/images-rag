import fitz  # PyMuPDF
import os
from pathlib import Path
import chromadb
import requests

# --- Setup ---
# Resolve paths relative to this script's directory so execution works from any CWD
script_dir = Path(__file__).resolve().parent
pdf_path = script_dir / "sample3.pdf"
images_folder = script_dir / "images"
os.makedirs(images_folder, exist_ok=True)

# Connect to Chroma (store DB alongside scripts for consistency)
chroma_dir = script_dir / "chroma_db"
client = chromadb.PersistentClient(path=str(chroma_dir))
collection = client.get_or_create_collection("pdf_chunks")


# --- Embedding function (Ollama) ---
def get_embedding(input_text: str):
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

        # 👀 Debug response
        print("\n--- Raw embedding response ---")
        print(data)

        return data.get("embedding")
    except requests.RequestException as e:
        print(f"⚠️ Embedding HTTP error for text: {input_text[:50]}... Error: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"⚠️ Embedding parse error for text: {input_text[:50]}... Error: {e}")
        return None


# --- Open PDF ---
doc = fitz.open(pdf_path)

chunk_id = 0
for page_num, page in enumerate(doc, start=1):
    page_text = page.get_text().strip()
    if not page_text:
        continue

    image_paths = []
    for img_index, img in enumerate(page.get_images(full=True), start=1):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        image_path = images_folder / f"page{page_num}_img{img_index}.png"
        # Save to absolute path on disk
        pix.save(str(image_path))
        # Store relative path in metadata for frontend consumption
        relative_path = f"images/page{page_num}_img{img_index}.png"
        image_paths.append(relative_path)

    embedding = get_embedding(page_text)
    if embedding is None:
        print(f"⚠️ Skipping page {page_num}, embedding unavailable.")
        continue

    collection.add(
        documents=[page_text],
        embeddings=[embedding],
        metadatas=[{"page": page_num, "images": ", ".join(image_paths)}],
        ids=[str(chunk_id)],
    )
    chunk_id += 1

print("\n✅ Indexed PDF into Chroma with text + image references!")
print(f"📊 Total docs in collection: {collection.count()}")
