import json
from ollama import chat

# -----------------------------
# 1. Load cleaned tender
# -----------------------------

input_path = "extracted/cleaned_tender_pages.json"

with open(input_path, "r", encoding="utf-8") as f:
    pages = json.load(f)


# -----------------------------
# 2. Select ONE page
# -----------------------------

page = pages[10]       # Page 8

page_text = page["text"]


# Include tables if present
for table in page["tables"]:
    page_text += "\nTABLE:\n"

    for row in table:
        page_text += " | ".join(
            str(cell) if cell is not None else ""
            for cell in row
        )

        page_text += "\n"


# -----------------------------
# 3. Create prompt
# -----------------------------

prompt = f"""
You are an AI assistant extracting bidder compliance requirements
from ONE PAGE of a GOODS procurement tender.

Your task is ONLY to identify requirements that can be checked
against documents submitted by a bidder.

A bidder requirement is something the bidder must:
- satisfy
- provide
- submit
- comply with
- demonstrate
- declare
- certify
- offer

Do NOT summarize the page.

Do NOT invent information.

Use ONLY information present on this page.

Do NOT change or convert:
- numbers
- currencies
- units
- dates
- percentages
- durations

Preserve the original meaning and values from the page.


CATEGORIES:

1. ELIGIBILITY
Basic conditions for bidder eligibility.
Examples of evidence:
GST/PAN, registration documents, eligibility declarations,
non-blacklisting declarations.

2. EXPERIENCE_QUALIFICATION
Past experience, similar supplies, qualification and performance
requirements.
Examples of evidence:
purchase orders, supply orders, experience certificates,
completion certificates, performance statements.

3. TECHNICAL
Product specifications, characteristics and functional requirements.
Examples of evidence:
technical proposal, datasheet, catalogue, technical
compliance statement.

4. CERTIFICATION_QUALITY
Required standards, certifications, testing and quality requirements.
Examples of evidence:
BIS certificate, ISO certificate, test certificate,
quality certificate.

5. DELIVERY
Requirements concerning quantity, delivery period, destination
or delivery schedule.
Examples of evidence:
delivery commitment, undertaking, supply schedule,
bidder's offer.

6. FINANCIAL
Financial capability and financial security requirements.
Examples of evidence:
turnover certificate, audited financial statements,
CA certificate, EMD, bid security, performance security.

7. COMMERCIAL
Price, taxes, payment and other commercial requirements that
can be checked from the bidder's submission.
Examples of evidence:
BOQ, price bid, commercial offer, tax details.

8. LEGAL_DOCUMENTARY
Mandatory declarations, undertakings, affidavits, authorizations
and required bid documents/forms.
Examples of evidence:
declaration, undertaking, affidavit, authorization letter,
required tender form.


SUBCATEGORY:

For every requirement, create a short and meaningful
subcategory yourself based on the actual requirement.

Examples:
TURNOVER
SIMILAR_SUPPLY_EXPERIENCE
NON_BLACKLISTING_DECLARATION
RAM
BIS_CERTIFICATION
DELIVERY_PERIOD
PERFORMANCE_SECURITY

Do not use a generic subcategory such as "OTHER" unless absolutely necessary.


IMPORTANT:

The expected_evidence field should contain the type of bidder
document or evidence that could prove the requirement.

Do NOT assume that a bidder has submitted the document.
You are only identifying what evidence would be expected.


OUTPUT:

Return ONLY a valid JSON array.

For every requirement use this structure:

[
    {{
        "requirement_id": "REQ_001",
        "category": "FINANCIAL",
        "subcategory": "TURNOVER",
        "requirement": "Original requirement wording",
        "source_page": 8
    }}
]

If there are no bidder compliance requirements on this page,
return:

[]


PAGE NUMBER:
{page["page"]}


PAGE CONTENT:

{page_text}
"""


# -----------------------------
# 4. Send to Qwen
# -----------------------------

response = chat(
    model="qwen2.5:3b",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)


# -----------------------------
# 5. Print result
# -----------------------------

result = response.message.content

print("\nMODEL RESPONSE:\n")
print(result)