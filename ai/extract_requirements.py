import json
import ollama
import os

input_path = "extracted/cleaned_tender_pages.json"
output_path = "extracted/requirements_raw.json"

# Load cleaned tender pages
with open(input_path, "r", encoding="utf-8") as f:
    pages = json.load(f)

all_requirements = []

for page in pages:

    page_number = page["page"]
    text = page["text"]

    print(f"\nProcessing page {page_number}...")

    # Skip empty pages
    if not text.strip():
        print("Empty page. Skipping.")
        continue

    prompt = f"""
You are extracting requirements from a government goods procurement tender.

Read ONLY the tender page below.

Your task is to identify requirements that can later be checked against
documents submitted by a bidder.

Include requirements related to:

1. ELIGIBILITY
2. EXPERIENCE / QUALIFICATION
3. TECHNICAL
4. CERTIFICATION / QUALITY
5. DELIVERY
6. FINANCIAL
7. COMMERCIAL
8. LEGAL / DOCUMENTARY

Important rules:

- Extract only actual requirements stated on this page.
- Do NOT invent information.
- Do NOT summarize the whole page.
- Copy the requirement closely from the source.
- Do NOT determine whether the requirement is mandatory.
- Do NOT identify expected evidence documents.
- Do NOT convert currencies or units.
- Do NOT calculate or normalize numeric values.
- Do NOT include general explanations or background information.
- Ignore instructions that are only about how the tender document itself
  is organized.
- Ignore completed bidder forms unless they contain a requirement that
  applies independently to the bidder.
- If there are no relevant bidder requirements on this page, return [].

Return ONLY valid JSON.

Format:

[
  {{
    "requirement_id": "REQ_001",
    "category": "TECHNICAL",
    "subcategory": "PROCESSOR",
    "requirement": "Exact or closely copied requirement text",
    "source_page": {page_number}
  }}
]

Tender page {page_number}:

{text}
"""

    try:
        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = response["message"]["content"].strip()

        # Remove markdown code fences if Qwen adds them
        if result.startswith("```"):
            result = result.replace("```json", "")
            result = result.replace("```", "")
            result = result.strip()

        page_requirements = json.loads(result)

        # Add requirements from this page
        for req in page_requirements:
            all_requirements.append(req)

        print(f"Found {len(page_requirements)} requirements.")

    except json.JSONDecodeError:
        print(f"Invalid JSON returned for page {page_number}")
        print(result)

    except Exception as e:
        print(f"Error processing page {page_number}: {e}")


# Give IDs again globally so they are unique
for index, req in enumerate(all_requirements, start=1):
    req["requirement_id"] = f"REQ_{index:03d}"


# Create output directory
os.makedirs("extracted", exist_ok=True)

# Save results
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(
        all_requirements,
        f,
        indent=4,
        ensure_ascii=False
    )

print("\n--------------------------------")
print("Requirement extraction completed.")
print("Total requirements:", len(all_requirements))
print("Saved to:", output_path)
print("--------------------------------")