import fitz  # PyMuPDF
import os
from pathlib import Path
import chromadb
import requests
from typing import List, Dict, Any, Tuple

# --- Setup ---
# Resolve paths relative to this script's directory so execution works from any CWD
script_dir = Path(__file__).resolve().parent
pdf_path = script_dir / "sample3.pdf"
images_folder = script_dir / "images"
os.makedirs(images_folder, exist_ok=True)

# Connect to Chroma (store DB alongside scripts for consistency)
chroma_dir = script_dir / "chroma_db"
client = chromadb.PersistentClient(path=str(chroma_dir))

# Optional: reset collection for a clean PoC re-index
RESET_COLLECTION = True
if RESET_COLLECTION:
    try:
        client.delete_collection("pdf_chunks")
    except Exception:
        pass

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


# --- Helpers for layout-aware chunking ---
def rect_center(rect: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x0, y0, x1, y1 = rect
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def rects_intersect(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)


def expand_rect(
    rect: Tuple[float, float, float, float], px: float
) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = rect
    return (x0 - px, y0 - px, x1 + px, y1 + px)


# --- Open PDF and build spatial chunks ---
doc = fitz.open(pdf_path)

chunk_id = 0
for page_num, page in enumerate(doc, start=1):
    layout = page.get_text("dict")
    if not layout or "blocks" not in layout:
        continue

    # Separate text blocks and image blocks with their bboxes
    text_blocks: List[Dict[str, Any]] = []
    image_blocks: List[Dict[str, Any]] = []

    for block in layout["blocks"]:
        btype = block.get("type", 0)
        bbox = tuple(block.get("bbox", (0, 0, 0, 0)))  # type: ignore
        if btype == 0:
            # Concatenate all lines / spans into a single text for this block
            lines = block.get("lines", [])
            parts: List[str] = []
            for ln in lines:
                spans = ln.get("spans", [])
                parts.extend([sp.get("text", "") for sp in spans])
            text = " ".join([p.strip() for p in parts]).strip()
            if text:
                text_blocks.append({"text": text, "bbox": bbox})
        elif btype == 1:
            # Image block
            image_blocks.append({"bbox": bbox, "xref": block.get("xref")})

    if not text_blocks and not image_blocks:
        continue

    # Save images and prepare their metadata
    saved_images: List[Dict[str, Any]] = []
    for idx, ib in enumerate(image_blocks, start=1):
        xref = ib.get("xref")
        if not xref:
            continue
        try:
            pix = fitz.Pixmap(doc, int(xref))
        except Exception:
            continue
        image_path = images_folder / f"page{page_num}_img{idx}.png"
        pix.save(str(image_path))
        rel_path = f"images/page{page_num}_img{idx}.png"
        saved_images.append(
            {
                "bbox": tuple(ib["bbox"]),
                "path": rel_path,
            }
        )

    # Associate images to their nearest/overlapping text blocks
    # Strategy: if an image intersects an expanded text bbox, attach it. Otherwise, attach the nearest vertically adjacent text block.
    expanded_by = 12.0  # points
    for tb in text_blocks:
        tb["images"] = []  # will hold relative paths
    for img in saved_images:
        attached = False
        for tb in text_blocks:
            if rects_intersect(expand_rect(tb["bbox"], expanded_by), img["bbox"]):
                tb["images"].append(img["path"])
                attached = True
        if attached:
            continue
        # Fallback: nearest by center distance
        icx, icy = rect_center(img["bbox"])
        best_idx = None
        best_dist = float("inf")
        for i, tb in enumerate(text_blocks):
            tcx, tcy = rect_center(tb["bbox"])
            dist = (
                abs(icy - tcy) + abs(icx - tcx) * 0.25
            )  # weight vertical proximity higher
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx is not None:
            text_blocks[best_idx]["images"].append(img["path"])

    # Create a Chroma document per text block with its specific images
    for tb in text_blocks:
        text = tb["text"].strip()
        if not text:
            continue
        embedding = get_embedding(text)
        if embedding is None:
            print(f"⚠️ Skipping page {page_num} block, embedding unavailable.")
            continue
        metadata = {
            "page": page_num,
            "bbox": ",".join([str(v) for v in tb["bbox"]]),
            "images": ", ".join(sorted(set(tb.get("images", [])))),
        }
        collection.add(
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[str(chunk_id)],
        )
        chunk_id += 1

print(
    "\n✅ Indexed PDF into Chroma with layout-aware text chunks and associated images!"
)
print(f"📊 Total docs in collection: {collection.count()}")
