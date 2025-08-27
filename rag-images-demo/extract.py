import fitz  # PyMuPDF
import os

pdf_path = "sample3.pdf"   # make sure sample.pdf is in the same folder
doc = fitz.open(pdf_path)

os.makedirs("images", exist_ok=True)

for page_num, page in enumerate(doc, start=1):
    # Print some text
    text = page.get_text()
    print(f"\n--- Page {page_num} ---")
    print(text[:200])  # first 200 characters

    # Save images
    for img_index, img in enumerate(page.get_images(full=True), start=1):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        image_path = f"images/page{page_num}_img{img_index}.png"
        pix.save(image_path)
        print(f"Saved image: {image_path}")
