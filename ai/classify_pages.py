import json
import re
import ollama

INPUT_PATH = "extracted/cleaned_tender_pages.json"
OUTPUT_PATH = "extracted/classified_pages.json"

MODEL = "qwen2.5:3b"


# --------------------------------------------------
# STEP 1: Cheap Python candidate filter
# --------------------------------------------------

RELEVANCE_PATTERNS = [
    r"\beligib\w*\b",
    r"\bqualif\w*\b",
    r"\brequirement\w*\b",
    r"\bspecification\w*\b",
    r"\btechnical\b",
    r"\bturnover\b",
    r"\bexperience\b",
    r"\bcertificate\w*\b",
    r"\bauthori[sz]ation\b",
    r"\bblacklist\w*\b",
    r"\bdebar\w*\b",
    r"\bdelivery\b",
    r"\bwarranty\b",
    r"\bbid security\b",
    r"\bearnest money\b",
    r"\bEMD\b",
    r"\bperformance security\b",
    r"\bshall\b",
    r"\bmust\b",
    r"\bsubmit\b",
    r"\bprovide\b",
    r"\bminimum\b",
    r"\bmandatory\b",
]


def is_candidate(text):
    """
    Cheap first-pass filter.

    This DOES NOT decide whether a page is relevant.
    It only decides whether the page deserves
    semantic checking by the LLM.
    """

    text_lower = text.lower()

    matches = 0

    for pattern in RELEVANCE_PATTERNS:
        if re.search(pattern, text_lower):
            matches += 1

    # Require at least 2 signals.
    return matches >= 2


# --------------------------------------------------
# STEP 2: LLM semantic classification
# --------------------------------------------------

def classify_with_llm(page_number, text):

    prompt = f"""
You are a procurement tender document analysis system.

We need to identify pages that contain REQUIREMENTS
that can be evaluated against a bidder's submitted bid documents.

Page number: {page_number}

PAGE CONTENT:
----------------
{text}
----------------

Classify this page as exactly one of:

RELEVANT
NOT_RELEVANT

Mark a page RELEVANT if it contains requirements such as:

- bidder eligibility
- qualification criteria
- financial requirements
- experience requirements
- technical specifications
- certifications or quality requirements
- required declarations or undertakings
- required authorizations
- bid security / EMD requirements
- delivery commitments that must be met by the bidder
- warranty or service commitments that form part of bid evaluation
- documents that the bidder is required to submit

Mark a page NOT_RELEVANT if it mainly contains:

- table of contents
- definitions with no bidder requirement
- general background/information
- post-award contract administration
- payment procedure only
- termination clauses
- dispute-resolution clauses
- completed bidder forms
- bidder's already-filled answers
- document indexes
- requirement registers or summaries
- annexures that merely repeat bidder responses

IMPORTANT:
A page may contain words like "shall", "must", "submit", or
"requirement" and still be NOT_RELEVANT if those statements
are only post-award contractual obligations.

Return ONLY valid JSON.

Format:

{{
    "page": {page_number},
    "classification": "RELEVANT",
    "reason": "Short explanation"
}}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = response["message"]["content"].strip()

    # Remove accidental markdown code fences
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        print(f"Could not parse Qwen output for page {page_number}")
        print(content)

        result = {
            "page": page_number,
            "classification": "NOT_RELEVANT",
            "reason": "LLM output could not be parsed."
        }

    return result


# --------------------------------------------------
# MAIN
# --------------------------------------------------

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    pages = json.load(f)


results = []

for page in pages:

    page_number = page["page"]
    text = page["text"]

    print(f"\nChecking page {page_number}...")

    # Empty page
    if not text.strip():
        results.append({
            "page": page_number,
            "classification": "NOT_RELEVANT",
            "method": "python",
            "reason": "Page contains no extracted text."
        })
        continue

    # First cheap filter
    candidate = is_candidate(text)

    if not candidate:

        print("  → Rejected by Python filter")

        results.append({
            "page": page_number,
            "classification": "NOT_RELEVANT",
            "method": "python",
            "reason": "No sufficient requirement-related signals."
        })

        continue

    # Only candidates reach Qwen
    print("  → Candidate, sending to Qwen...")

    result = classify_with_llm(page_number, text)

    result["method"] = "llm"

    results.append(result)

    print(
        f"  → {result.get('classification')} "
        f"| {result.get('reason')}"
    )


# Save results
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4, ensure_ascii=False)


print("\n--------------------------------")
print("Page classification completed.")
print("Saved to:", OUTPUT_PATH)
print("--------------------------------")