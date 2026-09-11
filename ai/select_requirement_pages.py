import json
import re
import os

input_path = "extracted/cleaned_tender_pages.json"
output_path = "extracted/relevant_tender_pages.json"


# Words that indicate an actual requirement
REQUIREMENT_PATTERNS = [
    r"\bshall\b",
    r"\bmust\b",
    r"\brequired\b",
    r"\bminimum\b",
    r"\bat least\b",
    r"\bnot less than\b",
    r"\bnot exceed\b",
    r"\bshould be\b",
    r"\bis required\b",
    r"\bto be submitted\b",
    r"\bsubmit\b",
    r"\bprovide\b",
    r"\bdeclare\b",
]


# Sections that should never be used as the primary source
EXCLUDE_KEYWORDS = [
    "requirement register",
    "evidence document index",
    "document classification test set",
    "table of contents",
    "sample bidder",
    "completed bidder",
]


# Strong section headings
SECTION_KEYWORDS = [
    "eligibility criteria",
    "qualification criteria",
    "qualification requirements",
    "technical specifications",
    "technical requirements",
    "quality assurance",
    "delivery requirements",
    "commercial requirements",
    "financial criteria",
]


def contains_requirement_language(text):
    """
    Check whether the page contains language that looks
    like an actual procurement requirement.
    """

    text_lower = text.lower()

    matches = []

    for pattern in REQUIREMENT_PATTERNS:
        if re.search(pattern, text_lower):
            matches.append(pattern)

    return matches


def contains_strong_section(text):
    """
    Check whether the page appears to contain an actual
    requirement section.
    """

    text_lower = text.lower()

    matches = []

    for keyword in SECTION_KEYWORDS:
        if keyword in text_lower:
            matches.append(keyword)

    return matches


with open(input_path, "r", encoding="utf-8") as f:
    pages = json.load(f)


relevant_pages = []


for page in pages:

    page_number = page["page"]
    text = page["text"]

    text_lower = text.lower()


    # -----------------------------------------
    # 1. Explicit exclusions
    # -----------------------------------------

    excluded_keyword = None

    for keyword in EXCLUDE_KEYWORDS:
        if keyword in text_lower:
            excluded_keyword = keyword
            break

    if excluded_keyword:

        print(
            f"Page {page_number}: EXCLUDED "
            f"(contains '{excluded_keyword}')"
        )

        continue


    # -----------------------------------------
    # 2. Look for actual requirement language
    # -----------------------------------------

    requirement_matches = contains_requirement_language(text)


    # -----------------------------------------
    # 3. Look for strong section headings
    # -----------------------------------------

    section_matches = contains_strong_section(text)


    # -----------------------------------------
    # 4. Decide whether to include page
    # -----------------------------------------

    # Strong section + requirement language
    if section_matches and requirement_matches:

        relevant_pages.append({
            "page": page_number,
            "text": text,
            "reason": "section + requirement language",
            "matched_sections": section_matches,
            "matched_patterns": requirement_matches
        })

        print(
            f"Page {page_number}: INCLUDED "
            f"(section + requirement language)"
        )

    # Requirement language alone
    elif requirement_matches:

        relevant_pages.append({
            "page": page_number,
            "text": text,
            "reason": "requirement language",
            "matched_sections": [],
            "matched_patterns": requirement_matches
        })

        print(
            f"Page {page_number}: INCLUDED "
            f"(requirement language)"
        )

    else:

        print(
            f"Page {page_number}: SKIPPED"
        )


# -----------------------------------------
# Save result
# -----------------------------------------

os.makedirs("extracted", exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(
        relevant_pages,
        f,
        indent=4,
        ensure_ascii=False
    )


print("\n--------------------------------")
print("Page filtering completed.")
print("Total tender pages:", len(pages))
print("Relevant pages:", len(relevant_pages))
print("Saved to:", output_path)
print("--------------------------------")