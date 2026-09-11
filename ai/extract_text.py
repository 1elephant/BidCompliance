import pdfplumber
import json
import os

pdf_path = "data/sample_tender.pdf"
output_path = "extracted/tender_pages.json"

pages = []

with pdfplumber.open(pdf_path) as pdf:

    print("Number of pages:", len(pdf.pages))
    for page_number, page in enumerate(pdf.pages, start=1):
        # Extract normal text
        text = page.extract_text() or ""
        # Extract tables
        tables = page.extract_tables()
        page_data = {
            "page": page_number,
            "text": text,
            "tables": tables
        }
        pages.append(page_data)
os.makedirs("extracted", exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(
        pages,
        f,
        indent=4,
        ensure_ascii=False
    )
print("Extraction completed.")
print("Saved to:", output_path)   