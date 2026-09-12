import json
import re
import os


# ============================================================
# SETTINGS
# ============================================================

INPUT_PATH = "extracted/cleaned_tender_pages.json"
OUTPUT_PATH = "extracted/context_windows.json"

# Characters around a keyword match
CONTEXT_BEFORE = 300
CONTEXT_AFTER = 600

# If two windows are this close, merge them
MERGE_GAP = 150

# Number of pages to test
# Use None to process all pages
TEST_PAGES = 10


# ============================================================
# REQUIREMENT ANCHORS
# ============================================================

# Strong phrases are more reliable than individual words.
STRONG_ANCHORS = [

    # Bidder obligations
    "bidder shall",
    "bidder must",
    "bidder is required",
    "bidder should",

    "shall submit",
    "must submit",
    "should submit",

    "shall provide",
    "must provide",

    "shall furnish",
    "must furnish",

    "shall upload",
    "must upload",

    # Eligibility / qualification
    "eligible bidder",
    "eligible bidders",
    "eligibility",
    "qualification",
    "qualifying criteria",
    "qualification criteria",

    # Experience
    "similar experience",
    "past experience",
    "relevant experience",

    # Financial
    "minimum turnover",
    "annual turnover",
    "average annual turnover",

    "bid security",
    "earnest money",
    "earnest money deposit",
    "performance security",

    # Technical
    "technical specification",
    "technical specifications",
    "technical compliance",
    "technical requirement",
    "technical requirements",

    # Documents
    "submit certificate",
    "submit certificates",
    "submit declaration",
    "submit undertaking",
    "submit affidavit",
    "submit authorization",
    "submit authorisation",

    # OEM
    "oem authorization",
    "oem authorisation",
    "manufacturer authorization",
    "manufacturer authorisation",

    # Local content
    "local content",
    "class-i local supplier",
    "class-ii local supplier",

    # Delivery / warranty
    "delivery period",
    "delivery schedule",
    "warranty period",
    "comprehensive warranty",
    "camc",

    # Bid conditions
    "bid validity",
    "bid validity period",
    "responsive bid",
    "technically responsive"
]


# Individual terms.
# These are weaker and should generally require another signal nearby.

WEAK_ANCHORS = [

    "mandatory",
    "required",
    "shall",
    "must",
    "submit",
    "provide",
    "furnish",
    "upload",

    "experience",
    "turnover",
    "eligibility",
    "qualification",

    "certificate",
    "certification",
    "declaration",
    "undertaking",
    "affidavit",
    "authorization",
    "authorisation",

    "specification",
    "specifications",
    "technical",
    "compliance",

    "capacity",
    "dimension",
    "dimensions",
    "accuracy",
    "resolution",
    "sensitivity",
    "frequency",
    "voltage",
    "power",
    "temperature",
    "pressure",
    "material",
    "performance",

    "delivery",
    "warranty",

    "emd",
    "turnover",
    "price",
    "financial",

    "gst",
    "pan"
]


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_for_search(text):

    # Keep original text unchanged.
    # This normalized copy is ONLY used for locating matches.

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# ============================================================
# FIND ANCHOR POSITIONS
# ============================================================

def find_anchor_positions(text):

    normalized = normalize_for_search(text)

    matches = []

    # --------------------------------------------------------
    # Strong anchors
    # --------------------------------------------------------

    for anchor in STRONG_ANCHORS:

        start = 0

        while True:

            position = normalized.find(
                anchor.lower(),
                start
            )

            if position == -1:
                break

            matches.append({
                "position": position,
                "anchor": anchor,
                "strength": "STRONG"
            })

            start = position + len(anchor)


    # --------------------------------------------------------
    # Weak anchors
    # --------------------------------------------------------

    for anchor in WEAK_ANCHORS:

        start = 0

        while True:

            position = normalized.find(
                anchor.lower(),
                start
            )

            if position == -1:
                break

            matches.append({
                "position": position,
                "anchor": anchor,
                "strength": "WEAK"
            })

            start = position + len(anchor)


    # Remove duplicate positions
    # Example: "bidder shall" and "shall" may match together.

    unique = {}

    for match in matches:

        key = (
            match["position"],
            match["anchor"]
        )

        unique[key] = match

    matches = list(unique.values())

    matches.sort(
        key=lambda x: x["position"]
    )

    return matches


# ============================================================
# MERGE WINDOWS
# ============================================================

def merge_windows(windows):

    if not windows:
        return []

    windows.sort(
        key=lambda x: x["start"]
    )

    merged = []

    current = windows[0].copy()

    for next_window in windows[1:]:

        # If next window overlaps or is very close,
        # combine them.

        if next_window["start"] <= (
            current["end"] + MERGE_GAP
        ):

            current["end"] = max(
                current["end"],
                next_window["end"]
            )

            current["anchors"].extend(
                next_window["anchors"]
            )

        else:

            merged.append(current)

            current = next_window.copy()

    merged.append(current)

    # Remove duplicate anchor entries
    for window in merged:

        seen = set()
        clean_anchors = []

        for anchor in window["anchors"]:

            key = (
                anchor["anchor"],
                anchor["position"],
                anchor["strength"]
            )

            if key not in seen:

                seen.add(key)
                clean_anchors.append(anchor)

        window["anchors"] = clean_anchors

    return merged


# ============================================================
# CREATE CONTEXT WINDOWS FOR ONE PAGE
# ============================================================

def create_page_windows(page):

    page_number = page["page"]
    text = page.get("text", "")

    if not text.strip():

        return []

    matches = find_anchor_positions(text)

    windows = []

    for match in matches:

        position = match["position"]

        start = max(
            0,
            position - CONTEXT_BEFORE
        )

        end = min(
            len(text),
            position + CONTEXT_AFTER
        )

        windows.append({
            "start": start,
            "end": end,
            "anchors": [
                {
                    "anchor": match["anchor"],
                    "position": position,
                    "strength": match["strength"]
                }
            ]
        })

    return merge_windows(windows)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("CONTEXT WINDOW GENERATOR")
print("=" * 70)

with open(
    INPUT_PATH,
    "r",
    encoding="utf-8"
) as f:

    pages = json.load(f)

print(
    "Total pages:",
    len(pages)
)


# ============================================================
# TEST PAGE LIMIT
# ============================================================

pages_to_process = pages

if TEST_PAGES is not None:

    pages_to_process = pages[
        :TEST_PAGES
    ]

print(
    "Pages being tested:",
    len(pages_to_process)
)

print()


# ============================================================
# CREATE WINDOWS
# ============================================================

all_contexts = []

context_counter = 1

for page in pages_to_process:

    page_number = page["page"]
    text = page.get("text", "")

    windows = create_page_windows(
        page
    )

    print(
        f"Page {page_number}: "
        f"{len(windows)} context windows"
    )

    for window in windows:

        start = window["start"]
        end = window["end"]

        context_text = text[start:end].strip()

        context = {
            "context_id":
                f"CTX_{context_counter:04d}",

            "page":
                page_number,

            "start_char":
                start,

            "end_char":
                end,

            "anchors":
                window["anchors"],

            "text":
                context_text
        }

        all_contexts.append(
            context
        )

        context_counter += 1


# ============================================================
# SAVE
# ============================================================

os.makedirs(
    os.path.dirname(OUTPUT_PATH),
    exist_ok=True
)

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        all_contexts,
        f,
        indent=4,
        ensure_ascii=False
    )


# ============================================================
# PRINT CONTEXTS
# ============================================================

print()
print("=" * 70)
print("GENERATED CONTEXTS")
print("=" * 70)

for context in all_contexts:

    print()
    print(
        "=" * 70
    )

    print(
        f"{context['context_id']} "
        f"| PAGE {context['page']}"
    )

    print(
        "-" * 70
    )

    print(
        "ANCHORS:"
    )

    for anchor in context["anchors"]:

        print(
            f"  [{anchor['strength']}] "
            f"{anchor['anchor']}"
        )

    print()
    print(
        "CONTEXT:"
    )

    print(
        context["text"]
    )

    print(
        "=" * 70
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

print(
    "Pages processed:",
    len(pages_to_process)
)

print(
    "Context windows:",
    len(all_contexts)
)

print()
print(
    "Saved to:",
    OUTPUT_PATH
)

