import fitz  # PyMuPDF
import os
from pathlib import Path

# Use script-relative paths
script_dir = Path(__file__).resolve().parent
pdf_path = script_dir / "sample3.pdf"  # make sure sample is here
doc = fitz.open(str(pdf_path))

images_dir = script_dir / "images"
os.makedirs(images_dir, exist_ok=True)

for page_num, page in enumerate(doc, start=1):
    # Print some text
    text = page.get_text()
    print(f"\n--- Page {page_num} ---")
    print(text[:200])  # first 200 characters

    # Save images
    for img_index, img in enumerate(page.get_images(full=True), start=1):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        image_path = images_dir / f"page{page_num}_img{img_index}.png"
        pix.save(str(image_path))
        print(f"Saved image: {image_path}")
