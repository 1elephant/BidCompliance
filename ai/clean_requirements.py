import json
import os
import re
from difflib import SequenceMatcher


# ============================================================
# PATHS
# ============================================================

INPUT_PATH = "extracted/requirements_raw.json"
OUTPUT_PATH = "extracted/requirements.json"
REPORT_PATH = "extracted/requirements_validation_report.json"


# ============================================================
# ALLOWED VALUES
# ============================================================

ALLOWED_CATEGORIES = {
    "ELIGIBILITY",
    "EXPERIENCE / QUALIFICATION",
    "TECHNICAL",
    "CERTIFICATION / QUALITY",
    "DELIVERY",
    "FINANCIAL",
    "COMMERCIAL",
    "LEGAL / DOCUMENTARY",
}

ALLOWED_TYPES = {
    "MANDATORY",
    "CONDITIONAL",
}


# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_text(text):
    """
    Normalize text only for comparison.

    IMPORTANT:
    We do NOT replace the original requirement text.
    """
    if not isinstance(text, str):
        return ""

    text = text.lower()

    # Normalize common punctuation
    text = re.sub(r"[^\w\s%₹.-]", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def similarity(a, b):
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def is_valid_structure(req):
    """
    Check basic JSON structure and allowed values.
    """

    if not isinstance(req, dict):
        return False, "Not an object"

    required_fields = [
        "category",
        "requirement",
        "requirement_type",
    ]

    for field in required_fields:
        if field not in req:
            return False, f"Missing field: {field}"

    if not isinstance(req["requirement"], str):
        return False, "Requirement is not a string"

    if not req["requirement"].strip():
        return False, "Empty requirement"

    if req["category"] not in ALLOWED_CATEGORIES:
        return False, f"Invalid category: {req['category']}"

    if req["requirement_type"] not in ALLOWED_TYPES:
        return False, f"Invalid requirement type: {req['requirement_type']}"

    return True, None


# ============================================================
# HALLUCINATION / AUTHORITY CHECKS
# ============================================================

def looks_like_hallucinated_emd(req):
    """
    Detect the specific EMD hallucination pattern observed
    in the current Qwen output.

    We ONLY remove the generic EMD statement when it comes
    from contexts where the source context did not contain EMD.

    Page 2 and Page 5 are known EMD contexts.
    """

    text = normalize_text(req.get("requirement", ""))

    if "emd" not in text:
        return False

    generic_emd_patterns = [
        "the bidder shall furnish emd",
        "the tenderer bidder shall furnish emd",
        "the tenderer/bidder shall furnish emd",
    ]

    is_generic = any(
        pattern in text
        for pattern in generic_emd_patterns
    )

    if not is_generic:
        return False

    context_id = req.get("_context_id")
    page = req.get("_page")

    # EMD is genuinely mentioned in these contexts.
    legitimate_emd_contexts = {
        "CTX_0002",
        "CTX_0005",
    }

    if context_id in legitimate_emd_contexts:
        return False

    if page in {2, 5}:
        return False

    # Generic EMD appearing elsewhere is suspicious.
    return True


def looks_like_authority_right(req):
    """
    A purchaser/authority right is not itself a bidder requirement.

    Example:
    'Midhani has the right to disqualify any supplier...'
    """

    text = normalize_text(req.get("requirement", ""))

    authority_phrases = [
        "has the right to disqualify",
        "reserves the right to",
        "may disqualify",
        "may reject",
        "reserves its right",
        "purchaser may",
        "midhani may",
        "midhani has the right",
    ]

    return any(
        phrase in text
        for phrase in authority_phrases
    )


# ============================================================
# DUPLICATE HANDLING
# ============================================================

def is_duplicate_of_existing(req, existing):
    """
    Detect exact or very-near duplicate requirements.

    We deliberately use a fairly high threshold so that two
    genuinely different requirements are not accidentally merged.
    """

    current_text = req.get("requirement", "")

    for old in existing:

        old_text = old.get("requirement", "")

        # Exact normalized match
        if normalize_text(current_text) == normalize_text(old_text):
            return True, old

        # High similarity
        score = similarity(current_text, old_text)

        if score >= 0.90:
            return True, old

    return False, None


# ============================================================
# MERGE SOURCE INFORMATION
# ============================================================

def merge_source(existing, duplicate):
    """
    If two requirements are duplicates, preserve both source
    locations instead of losing evidence.

    Existing requirement keeps its original wording.
    """

    sources = existing.get("sources", [])

    if not sources:
        sources.append({
            "context_id": existing.get("_context_id"),
            "page": existing.get("_page"),
        })

    duplicate_source = {
        "context_id": duplicate.get("_context_id"),
        "page": duplicate.get("_page"),
    }

    if duplicate_source not in sources:
        sources.append(duplicate_source)

    existing["sources"] = sources

    # Remove internal single-source fields from final output.
    existing.pop("_context_id", None)
    existing.pop("_page", None)

    return existing


# ============================================================
# MAIN NORMALIZATION
# ============================================================

def main():

    print("=" * 70)
    print("REQUIREMENT NORMALIZATION + VALIDATION")
    print("=" * 70)

    print(f"Input : {INPUT_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print()

    raw_requirements = load_json(INPUT_PATH)

    if not isinstance(raw_requirements, list):
        raise ValueError("requirements_raw.json must contain a JSON list.")

    print(f"Raw requirements: {len(raw_requirements)}")
    print()

    clean_requirements = []
    removed_items = []
    merged_items = []

    # --------------------------------------------------------
    # PASS 1: STRUCTURE VALIDATION
    # --------------------------------------------------------

    for index, req in enumerate(raw_requirements):

        valid, reason = is_valid_structure(req)

        if not valid:

            removed_items.append({
                "original_index": index,
                "reason": reason,
                "requirement": req,
            })

            print(
                f"[REMOVE] #{index + 1}: {reason}"
            )

            continue

        # ----------------------------------------------------
        # PASS 2: HALLUCINATION CHECK
        # ----------------------------------------------------

        if looks_like_hallucinated_emd(req):

            removed_items.append({
                "original_index": index,
                "reason": "Likely hallucinated EMD requirement",
                "requirement": req,
            })

            print(
                f"[REMOVE] #{index + 1}: "
                f"Likely hallucinated EMD | "
                f"{req.get('_context_id')}"
            )

            continue

        # ----------------------------------------------------
        # PASS 3: AUTHORITY-RIGHT CHECK
        # ----------------------------------------------------

        if looks_like_authority_right(req):

            removed_items.append({
                "original_index": index,
                "reason": "Purchaser/authority right, not bidder requirement",
                "requirement": req,
            })

            print(
                f"[REMOVE] #{index + 1}: "
                f"Authority right | "
                f"{req.get('_context_id')}"
            )

            continue

        # ----------------------------------------------------
        # PASS 4: DUPLICATE CHECK
        # ----------------------------------------------------

        duplicate, existing = is_duplicate_of_existing(
            req,
            clean_requirements
        )

        if duplicate:

            merged = merge_source(existing, req)

            merged_items.append({
                "merged_requirement": req.get("requirement"),
                "kept_requirement": existing.get("requirement"),
                "source": {
                    "context_id": req.get("_context_id"),
                    "page": req.get("_page"),
                },
            })

            print(
                f"[MERGE] Duplicate requirement | "
                f"{req.get('_context_id')}"
            )

            continue

        # ----------------------------------------------------
        # KEEP
        # ----------------------------------------------------

        clean_requirements.append(req)

    # ========================================================
    # ASSIGN REQUIREMENT IDS
    # ========================================================

    final_requirements = []

    for index, req in enumerate(clean_requirements, start=1):

        output_req = {
            "requirement_id": f"REQ_{index:03d}",
            "category": req["category"],
            "requirement": req["requirement"],
            "requirement_type": req["requirement_type"],
        }

        # Preserve source information.
        if "sources" in req:
            output_req["sources"] = req["sources"]

        else:
            output_req["sources"] = [
                {
                    "context_id": req.get("_context_id"),
                    "page": req.get("_page"),
                }
            ]

        final_requirements.append(output_req)

    # ========================================================
    # VALIDATION REPORT
    # ========================================================

    report = {
        "summary": {
            "raw_requirements": len(raw_requirements),
            "final_requirements": len(final_requirements),
            "removed_requirements": len(removed_items),
            "merged_requirements": len(merged_items),
        },
        "removed": removed_items,
        "merged": merged_items,
    }

    # ========================================================
    # SAVE
    # ========================================================

    save_json(
        OUTPUT_PATH,
        final_requirements
    )

    save_json(
        REPORT_PATH,
        report
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    print()
    print("=" * 70)
    print("NORMALIZATION COMPLETED")
    print("=" * 70)

    print(
        f"Raw requirements      : {len(raw_requirements)}"
    )

    print(
        f"Final requirements    : {len(final_requirements)}"
    )

    print(
        f"Removed               : {len(removed_items)}"
    )

    print(
        f"Merged                : {len(merged_items)}"
    )

    print()

    print("FINAL REQUIREMENTS")
    print("-" * 70)

    for req in final_requirements:

        print(
            f"{req['requirement_id']} | "
            f"{req['category']} | "
            f"Page(s): "
            f"{', '.join(str(x['page']) for x in req['sources'])}"
        )

        print(
            f"  {req['requirement']}"
        )

        print(
            f"  Type: {req['requirement_type']}"
        )

        print()

    print("=" * 70)
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()