import fitz  # PyMuPDF
import os
import chromadb
import requests

# --- Setup ---
pdf_path = "sample3.pdf"
images_folder = "images"
os.makedirs(images_folder, exist_ok=True)

# Connect to Chroma
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("pdf_chunks")

# --- Embedding function (Ollama) ---
def get_embedding(text: str):
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

        # 👀 Debug response
        print(f"\n--- Raw embedding response ---")
        print(data)

        return data.get("embedding")
    except Exception as e:
        print(f"⚠️ Embedding failed for text: {text[:50]}... Error: {e}")
        return None

# --- Open PDF ---
doc = fitz.open(pdf_path)

chunk_id = 0
for page_num, page in enumerate(doc, start=1):
    text = page.get_text().strip()
    if not text:
        continue

    image_paths = []
    for img_index, img in enumerate(page.get_images(full=True), start=1):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        image_path = f"{images_folder}/page{page_num}_img{img_index}.png"
        pix.save(image_path)
        image_paths.append(image_path)

    embedding = get_embedding(text)
    if embedding is None:
        print(f"⚠️ Skipping page {page_num}, embedding unavailable.")
        continue

    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[{
            "page": page_num,
            "images": ", ".join(image_paths)
        }],
        ids=[str(chunk_id)]
    )
    chunk_id += 1

print("\n✅ Indexed PDF into Chroma with text + image references!")
print(f"📊 Total docs in collection: {collection.count()}")
