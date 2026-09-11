import json
import re
input_path = "extracted/tender_pages.json"
output_path = "extracted/cleaned_tender_pages.json"
def clean_text(text):
    # Remove extra spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n\s*\n+", "\n", text)

    # Remove spaces at the beginning/end of lines
    text = "\n".join(line.strip() for line in text.split("\n"))

    return text.strip()


with open(input_path, "r", encoding="utf-8") as f:
    pages = json.load(f)


cleaned_pages = []

for page in pages:

    cleaned_page = {
        "page": page["page"],
        "text": clean_text(page["text"]),
        "tables": page["tables"]
    }

    cleaned_pages.append(cleaned_page)


with open(output_path, "w", encoding="utf-8") as f:
    json.dump(
        cleaned_pages,
        f,
        indent=4,
        ensure_ascii=False
    )


print("Cleaning completed.")
print("Saved to:", output_path)