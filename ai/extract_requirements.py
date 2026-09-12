import json
import ollama
import time
import os
import re


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_PATH = "extracted/context_windows.json"
OUTPUT_PATH = "extracted/requirements_raw.json"

MODEL = "qwen2.5:3b"

# One context at a time is more reliable for a 3B model.
CONTEXTS_PER_BATCH = 1

# Ollama generation settings
TEMPERATURE = 0
NUM_CTX = 16384
NUM_PREDICT = 1500


# ============================================================
# BALANCED SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = r"""
You are a STRICT but BALANCED government tender requirement extraction
engine.

Your task is to extract genuine requirements from the CURRENT TENDER
CONTEXT ONLY.

You are NOT allowed to invent, complete, or assume information.

At the same time, do NOT be so restrictive that you discard a genuine
requirement merely because it is not an eligibility condition.

============================================================
1. SOURCE GROUNDING — HIGHEST PRIORITY
============================================================

The CURRENT TENDER CONTEXT is your ONLY source.

Every extracted requirement MUST be supported by words actually present
in the CURRENT TENDER CONTEXT.

You must NOT use:

- another context window
- another page
- previous model output
- information remembered from the tender
- general government procurement knowledge
- typical tender requirements
- assumptions about what later sections probably contain
- missing values
- missing dates
- missing thresholds
- missing documents
- missing technical specifications

If a requirement is not supported by the CURRENT TENDER CONTEXT,
do not extract it.

WHEN IN DOUBT, OMIT IT.

============================================================
2. WHAT IS A REQUIREMENT?
============================================================

A requirement is an explicit condition, obligation, specification,
restriction, declaration, document requirement, or contractual
requirement stated in the CURRENT TENDER CONTEXT.

A requirement can apply to:

A. THE BIDDER
B. THE BID/SUBMISSION
C. THE GOODS OR SERVICES OFFERED
D. THE CONTRACTOR/SUCCESSFUL BIDDER, when relevant to the tender

Examples of valid requirements:

"The bidder shall submit an OEM authorization."

"The bidder shall furnish EMD."

"The bidder must provide documentary evidence."

"The bidder shall indicate taxes and duties."

"The offered equipment shall comply with the specified standard."

"The contractor shall repair damages caused during installation."

"The contractor shall provide warranty for the supplied equipment."

All of these can be requirements if they are explicitly stated in the
CURRENT TENDER CONTEXT.

IMPORTANT:

Do NOT require the sentence to contain the exact words
"must" or "shall".

A requirement may also be clearly expressed through:

- is required to
- has to
- should provide
- shall comply
- will be required to
- will have to
- only ... may
- bids from ... will not be accepted
- ... is mandatory
- ... shall be provided
- ... shall be furnished
- ... shall be submitted

============================================================
3. BIDDER-CHECKABLE OR CONTRACT-CHECKABLE
============================================================

A requirement should normally be something an officer can use to check:

- bidder eligibility
- bidder qualification
- bidder documents
- bidder declarations
- bidder's financial obligations
- bidder's commercial offer
- bidder's technical offer
- offered goods/services
- delivery obligations
- warranty obligations
- contractor obligations

A requirement does NOT have to decide eligibility.

For example:

"Bidder shall furnish EMD."

This is valid even though EMD is not an eligibility criterion.

"Bidder shall indicate applicable taxes and duties."

This is valid even though it is a commercial requirement.

"The contractor shall repair damages caused during installation."

This is valid as a contractual requirement.

============================================================
4. WHAT TO EXTRACT
============================================================

Extract explicit requirements relating to:

------------------------------------------------------------
BIDDER ELIGIBILITY
------------------------------------------------------------

- eligible bidder categories
- OEM requirements
- manufacturer requirements
- authorized distributor requirements
- authorized agent requirements
- bidder registration
- restrictions on bidders
- prohibitions
- disqualification conditions
- local supplier conditions
- foreign bidder conditions
- MSE conditions
- land-border related conditions
- conditions for participation

------------------------------------------------------------
EXPERIENCE / QUALIFICATION
------------------------------------------------------------

- years of experience
- similar work experience
- similar contracts
- number of contracts
- minimum contract value
- past performance
- technical qualification
- financial qualification
- turnover
- other explicit qualification conditions

------------------------------------------------------------
FINANCIAL
------------------------------------------------------------

- EMD
- bid security
- bid securing declaration
- security deposit
- performance security
- turnover
- financial thresholds
- financial declarations
- other financial obligations

Preserve:

- amount
- percentage
- deadline
- method
- exemption
- applicable bidder category

if explicitly present.

------------------------------------------------------------
DOCUMENTARY REQUIREMENTS
------------------------------------------------------------

Extract explicit requirements to:

- submit
- upload
- furnish
- attach
- provide
- sign
- declare
- certify
- submit along with the bid

Examples:

"The bidder shall submit the signed undertaking."

"Relevant documentary evidence shall be uploaded along with the bid."

"The bidder shall furnish the authorization letter."

A document name by itself is NOT enough.

For example:

"Annexure-V: Bid Security Declaration"

by itself is NOT a requirement.

But:

"The bidder shall submit the Bid Security Declaration in Annexure-V."

IS a requirement.

------------------------------------------------------------
TECHNICAL REQUIREMENTS
------------------------------------------------------------

Extract explicit technical requirements concerning:

- specifications
- quantity
- dimensions
- capacity
- performance
- material
- construction
- standards
- features
- accessories
- configuration
- quality
- accuracy
- tolerances
- operating conditions
- compatibility
- installation requirements
- testing requirements
- commissioning requirements

Preserve exact values.

Example:

"The system shall have a capacity of 1000 litres."

Extract the 1000 litre requirement.

Do NOT add specifications that are not present.

------------------------------------------------------------
DELIVERY
------------------------------------------------------------

Extract explicit requirements concerning:

- delivery period
- delivery location
- installation
- testing
- commissioning
- transportation
- completion period
- delivery schedule

Example:

"Material should be installed at Midhani at Rohtak Plant, Haryana."

This is a valid delivery/installation-related requirement if it is
explicitly stated.

------------------------------------------------------------
WARRANTY / SERVICE
------------------------------------------------------------

Extract explicit requirements concerning:

- warranty
- replacement
- repair
- maintenance
- CAMC
- service support
- defective parts
- service period

------------------------------------------------------------
COMMERCIAL
------------------------------------------------------------

Extract explicit bidder/bid obligations concerning:

- taxes
- duties
- prices
- deviations
- acceptance of terms
- bid validity
- commercial declarations
- other commercial conditions

------------------------------------------------------------
QUALITY / CERTIFICATION
------------------------------------------------------------

Extract explicit requirements concerning:

- BIS
- ISO
- relevant standards
- statutory standards
- quality certificates
- inspection certificates
- testing certificates
- compliance with codes/standards

============================================================
5. DEFINITIONS ARE NOT REQUIREMENTS
============================================================

Definitions by themselves are NOT requirements.

Example:

"Controlling ownership interest means ownership of more than
twenty-five percent..."

Do NOT extract it.

Example:

"'MSE' means Micro and Small Enterprise."

Do NOT extract it.

Example:

"Local supplier means a supplier having local content of 50% or more."

Do NOT extract the definition by itself.

However, if the context applies the definition to impose a condition,
extract the condition.

Example:

"Class-I Local Suppliers shall provide details of local content."

This IS a requirement.

Example:

"Any bidder from a country sharing a land border with India shall be
eligible only if registered with the Competent Authority."

This IS a requirement.

============================================================
6. INFORMATIONAL TEXT IS NOT A REQUIREMENT
============================================================

Do NOT extract purely informational or administrative statements.

Examples:

"Interested bidders may obtain information from the office of..."

NOT a requirement.

"The tender is available on the GeM portal."

NOT a requirement.

"The pre-bid meeting will be held on 10 December."

NOT a bidder requirement.

"The bid opening will take place on 15 December."

NOT a bidder requirement.

"MIDHANI is a Government of India Enterprise."

NOT a requirement.

However:

"Interested bidders shall submit their queries before 10 December."

IS a requirement because the bidder must take an action.

============================================================
7. TABLE OF CONTENTS / INDEX
============================================================

If the context is only a table of contents, checklist, section index,
or page-reference list, normally return:

[]

Examples:

"Eligibility Criteria ........ Page 12"

NOT a requirement.

"Technical Specifications ........ Pages 20-50"

NOT a requirement.

"General Terms and Conditions ........ Pages 51-60"

NOT a requirement.

Do NOT infer the contents of a referenced section.

IMPORTANT EXCEPTION:

If a checklist/table itself explicitly states an actual bidder action,
that action may be extracted.

Example:

"Bidder shall furnish EMD."

This is a requirement even if it appears inside a checklist/table.

============================================================
8. CHECKLISTS AND ATC TABLES
============================================================

Government tenders often contain tables such as:

S.No | Tender Requirement | Vendor Confirmation

These can contain REAL requirements.

Do NOT discard the entire table merely because it is a checklist.

For example:

"Supply the material as per MIDHANI Tender Quantity and Specification
without any deviation."

This is a requirement.

"Specify Agree/Disagree of GEM Tender Notice Inviting Tender All the
Terms and Conditions."

This may be a bidder response requirement and should be extracted if
the wording clearly requires the bidder to provide that confirmation.

Similarly:

"Bidder shall furnish Earnest Money Deposit (EMD)."

is a genuine financial requirement.

============================================================
9. CONDITIONAL REQUIREMENTS
============================================================

Use:

"MANDATORY"

when the requirement generally applies.

Use:

"CONDITIONAL"

when the requirement explicitly applies only under a stated condition.

Examples:

"EMD exemption is available for MSEs."

CONDITIONAL.

"If the bidder is from a country sharing a land border with India,
registration with the Competent Authority is required."

CONDITIONAL.

"Class-I Local Suppliers shall provide local content details."

CONDITIONAL.

"The bidder shall submit the signed undertaking."

MANDATORY.

Do NOT invent conditions.

============================================================
10. EXEMPTIONS
============================================================

Explicit exemptions can be extracted when they affect bidder
requirements.

Example:

"EMD exemption is available for MSEs."

Extract this as a CONDITIONAL requirement.

Do NOT infer other exemptions.

============================================================
11. PREFERENCES
============================================================

Explicit procurement preferences may be extracted when they create a
checkable bidder condition.

Example:

"Class-I local suppliers shall receive purchase preference."

This may be extracted as CONDITIONAL.

But a reference to a government policy alone is NOT enough.

Example:

"As per Government procurement policy..."

Do NOT create a requirement unless the context actually states the
condition/preference.

============================================================
12. RESTRICTIONS AND PROHIBITIONS
============================================================

Explicit restrictions are requirements.

Examples:

"Traders are excluded from the purview of the policy."

If this explicitly affects participation/benefit in the CURRENT CONTEXT,
extract the applicable condition carefully.

"Bids from banned bidders shall not be accepted."

IS a requirement.

"One distributor shall not represent more than one OEM."

IS a requirement.

Do not broaden the scope.

============================================================
13. CONTRACTOR / SUCCESSFUL BIDDER REQUIREMENTS
============================================================

Requirements applying after award can be extracted when they are part
of the tender's contractual scope and are explicitly stated.

Examples:

"The contractor shall repair damage caused during installation."

"The contractor shall replace defective components."

"The contractor shall guarantee that the work conforms to relevant
standards."

These are valid requirements.

However, do NOT extract purely internal purchaser actions or procedures.

============================================================
14. INCOMPLETE OR TRUNCATED TEXT
============================================================

The context may start or end in the middle of a sentence.

NEVER complete it using:

- another page
- another context
- general knowledge
- assumptions

If the visible text is sufficient to establish a complete requirement,
extract it.

If an important part is missing, omit it.

For example:

"Bidder shall furnish EMD of Rs."

If the amount is cut off and the amount is essential, do not invent it.

But if the visible text clearly establishes:

"Bidder shall furnish EMD."

then the basic EMD requirement may be extracted without inventing an
amount.

============================================================
15. PRESERVE IMPORTANT DETAILS
============================================================

When present, preserve:

- amounts
- percentages
- dates
- deadlines
- quantities
- thresholds
- time periods
- years
- contract values
- turnover values
- technical values
- dimensions
- capacities
- standards
- bidder categories
- authorities
- exemptions
- restrictions
- consequences

Do not silently remove important information.

============================================================
16. PARAPHRASING
============================================================

You may make small grammatical improvements.

Keep the meaning and important terminology close to the source.

Do NOT introduce facts.

Do NOT add:

- values
- dates
- percentages
- documents
- qualifications
- technical specifications
- authorities
- exceptions
- conditions

unless present in the CURRENT TENDER CONTEXT.

============================================================
17. SPLITTING REQUIREMENTS
============================================================

Extract one independently checkable requirement per item.

Split genuinely independent requirements.

Example:

"The bidder shall submit an OEM authorization and an experience
certificate."

This may be split into two requirements:

1. OEM authorization
2. experience certificate

But keep closely connected information together.

Example:

"The bidder shall furnish EMD of Rs. 5 lakh through NEFT before the
submission deadline."

Keep this as ONE requirement because amount, method and deadline describe
the same EMD obligation.

============================================================
18. DO NOT OVER-EXTRACT
============================================================

Do NOT turn every sentence into a requirement.

Do NOT extract:

- headings
- section titles
- definitions
- page numbers
- clause numbers
- contact information
- general descriptions
- purchaser background
- tender title
- tender reference number
- internal committee actions
- purchaser decisions
- bid opening schedules
- general government policy references
- statements that merely describe what the purchaser will do

============================================================
19. DO NOT UNDER-EXTRACT
============================================================

Do NOT reject a genuine requirement merely because:

- it appears in a table
- it is phrased as a confirmation
- it concerns EMD
- it concerns taxes
- it concerns delivery
- it concerns installation
- it concerns warranty
- it concerns a contractor
- it does not contain the exact word "shall"
- it is not an eligibility criterion

If the tender explicitly imposes an obligation or specification,
extract it.

============================================================
20. NO COMPLIANCE ANALYSIS
============================================================

Do NOT generate:

- compliance status
- compliant/non-compliant
- evidence
- evidence pages
- score
- ranking
- winner
- recommendation
- fraud determination
- risk score

Only extract the requirement.

============================================================
21. FINAL VALIDATION
============================================================

Before outputting EACH item, silently check:

1. Is it supported by the CURRENT TENDER CONTEXT?
2. Can I point to the words that support it?
3. Is it an actual obligation, condition, restriction, specification,
   qualification, or document requirement?
4. Does it apply to the bidder, bid, offered goods/services, or
   contractor/successful bidder?
5. Is it not merely a definition?
6. Is it not merely a heading?
7. Is it not merely a TOC entry?
8. Is it not merely contact information?
9. Is it not merely purchaser information?
10. Is it not merely a date/schedule?
11. Is it not merely a government policy reference?
12. Have I preserved important values and conditions?
13. Did I avoid inventing anything?
14. Did I avoid using another context?
15. Did I avoid completing missing text?

If ANY answer is NO, remove that item.

============================================================
22. IMPORTANT: OUTPUT FEW HIGH-CONFIDENCE ITEMS
============================================================

Accuracy is more important than quantity.

It is acceptable to return [] when there is genuinely no requirement.

However, when the context clearly contains requirements such as:

- "Bidder shall furnish EMD"
- "documentary evidence shall be uploaded"
- "bidder shall indicate taxes"
- "material shall be supplied without deviation"
- "contractor shall comply with relevant standards"
- "contractor shall repair damages"

those requirements MUST NOT be discarded merely because they are not
eligibility criteria.

============================================================
23. OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Do not return Markdown.

Do not return ```json.

Do not provide explanations.

Do not provide reasoning.

Use exactly:

[
  {
    "category": "FINANCIAL",
    "requirement": "The bidder shall furnish EMD.",
    "requirement_type": "MANDATORY"
  }
]

Allowed categories:

"ELIGIBILITY"
"EXPERIENCE / QUALIFICATION"
"TECHNICAL"
"CERTIFICATION / QUALITY"
"DELIVERY"
"FINANCIAL"
"COMMERCIAL"
"LEGAL / DOCUMENTARY"

Allowed requirement_type values:

"MANDATORY"
"CONDITIONAL"

If there are no genuine requirements in the CURRENT TENDER CONTEXT,
return exactly:

[]
"""


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    os.replace(temp_path, path)


def clean_json_response(text):
    """
    Extract JSON from the model response.

    Handles:
    - normal JSON
    - ```json ... ```
    - accidental surrounding text
    """

    text = text.strip()

    # Remove markdown fences
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    # Direct JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to locate JSON array
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def validate_requirement(item):
    """
    Basic structural validation.

    The LLM performs semantic validation through the prompt.
    This function prevents malformed output from entering the file.
    """

    if not isinstance(item, dict):
        return False

    required_keys = {
        "category",
        "requirement",
        "requirement_type"
    }

    if set(item.keys()) != required_keys:
        return False

    allowed_categories = {
        "ELIGIBILITY",
        "EXPERIENCE / QUALIFICATION",
        "TECHNICAL",
        "CERTIFICATION / QUALITY",
        "DELIVERY",
        "FINANCIAL",
        "COMMERCIAL",
        "LEGAL / DOCUMENTARY"
    }

    allowed_types = {
        "MANDATORY",
        "CONDITIONAL"
    }

    if item["category"] not in allowed_categories:
        return False

    if item["requirement_type"] not in allowed_types:
        return False

    if not isinstance(item["requirement"], str):
        return False

    if not item["requirement"].strip():
        return False

    return True


def normalize_requirements(items):
    """
    Remove malformed items and exact duplicates.
    """

    if not isinstance(items, list):
        return []

    valid = []
    seen = set()

    for item in items:

        if not validate_requirement(item):
            continue

        requirement = item["requirement"].strip()

        # Normalize whitespace only for duplicate detection.
        dedup_key = (
            item["category"],
            item["requirement_type"],
            re.sub(r"\s+", " ", requirement.lower())
        )

        if dedup_key in seen:
            continue

        seen.add(dedup_key)

        item["requirement"] = requirement

        valid.append(item)

    return valid


def get_context_text(context):
    """
    Support common structures used in context_windows.json.
    """

    if isinstance(context, str):
        return context

    if not isinstance(context, dict):
        return ""

    # Most likely keys first
    for key in [
        "context",
        "text",
        "content",
        "context_text",
        "page_text",
        "extracted_text"
    ]:
        value = context.get(key)

        if isinstance(value, str):
            return value

    return ""


def get_context_id(context, index):
    if isinstance(context, dict):
        return (
            context.get("context_id")
            or context.get("id")
            or f"CTX_{index + 1:04d}"
        )

    return f"CTX_{index + 1:04d}"


def get_page_number(context):
    if isinstance(context, dict):
        return (
            context.get("page")
            or context.get("page_number")
            or context.get("page_num")
        )

    return None


# ============================================================
# MAIN EXTRACTION
# ============================================================

def main():

    print("=" * 70)
    print("REQUIREMENT EXTRACTION")
    print("=" * 70)

    print(f"Input: {INPUT_PATH}")
    print(f"Model: {MODEL}")

    # --------------------------------------------------------
    # Load contexts
    # --------------------------------------------------------

    if not os.path.exists(INPUT_PATH):
        print(f"\nERROR: Input file not found: {INPUT_PATH}")
        return

    contexts = load_json(INPUT_PATH)

    if isinstance(contexts, dict):

        # Support files where contexts are stored under a key.
        if "contexts" in contexts:
            contexts = contexts["contexts"]
        elif "data" in contexts:
            contexts = contexts["data"]
        else:
            # Convert dictionary entries into list
            contexts = list(contexts.values())

    if not isinstance(contexts, list):
        print("\nERROR: context_windows.json does not contain a list.")
        return

    print(f"Total context windows: {len(contexts)}")

    # --------------------------------------------------------
    # Load checkpoint
    # --------------------------------------------------------

    if os.path.exists(OUTPUT_PATH):

        try:
            existing_output = load_json(OUTPUT_PATH)

            if not isinstance(existing_output, list):
                existing_output = []

        except Exception:
            print("\nWARNING: Existing output file is invalid.")
            print("Starting with empty results.")
            existing_output = []

    else:
        existing_output = []

    # --------------------------------------------------------
    # Determine already processed contexts
    # --------------------------------------------------------

    processed_contexts = set()

    for item in existing_output:

        if isinstance(item, dict):

            context_id = item.get("_context_id")

            if context_id:
                processed_contexts.add(context_id)

    print(f"Already processed contexts: {len(processed_contexts)}")

    print("\n" + "=" * 70)

    total_new_requirements = 0
    processed_count = 0

    # --------------------------------------------------------
    # Process each context
    # --------------------------------------------------------

    for index, context in enumerate(contexts):

        context_id = get_context_id(context, index)
        page_number = get_page_number(context)
        context_text = get_context_text(context)

        if context_id in processed_contexts:
            print(
                f"[{index + 1}/{len(contexts)}] "
                f"Skipping {context_id} (already processed)"
            )
            continue

        processed_count += 1

        print(
            f"[{index + 1}/{len(contexts)}] "
            f"Processing {context_id}"
            f"{f' | Page {page_number}' if page_number else ''}"
        )

        print(f"Context length: {len(context_text)} characters")

        print("-" * 70)

        # ----------------------------------------------------
        # Empty context
        # ----------------------------------------------------

        if not context_text.strip():

            print("Empty context -> []")

            extracted = []

        else:

            # Print preview for debugging
            preview = context_text[:2500]

            print(preview)

            if len(context_text) > 2500:
                print("\n[Context preview truncated for console display]")

            print("-" * 70)

            # ------------------------------------------------
            # User prompt
            # ------------------------------------------------

            user_prompt = f"""
CURRENT TENDER CONTEXT
======================

Context ID: {context_id}
Page: {page_number if page_number is not None else "unknown"}

The following text is the ONLY source you may use.

---------------- BEGIN CURRENT CONTEXT ----------------

{context_text}

----------------- END CURRENT CONTEXT -----------------

Extract genuine tender requirements from THIS context only.

FINAL REMINDER:

The text between BEGIN CURRENT CONTEXT and END CURRENT CONTEXT is the
ONLY evidence you may use.

If a requirement is not literally supported by that text, DO NOT output it.

For example, if another part of the tender says that EMD is required,
but the CURRENT CONTEXT does not mention EMD, you MUST NOT output EMD.

Do not remember EMD, warranty, eligibility, experience, technical
specifications, or any other requirement from earlier or later pages.

Do not output a requirement simply because it is common in this type of
tender.

Read the CURRENT CONTEXT first, identify the exact sentence supporting
each requirement, and then output only those requirements.

If there is no clearly supported requirement, output [].

Remember:

- Do not use information from other pages or contexts.
- Do not invent missing information.
- Do not convert definitions into requirements.
- Do not convert headings or TOC entries into requirements.
- Do extract explicit bidder/bid/technical/financial/documentary/
  delivery/warranty/contractor obligations.
- Return [] if there are no genuine requirements.

Return ONLY the JSON array.
"""

            # ------------------------------------------------
            # Call Ollama
            # ------------------------------------------------

            start_time = time.time()

            try:

                response = ollama.chat(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    options={
                        "temperature": TEMPERATURE,
                        "num_ctx": NUM_CTX,
                        "num_predict": NUM_PREDICT
                    }
                )

                elapsed = time.time() - start_time

                print(f"\nQwen processing time: {elapsed:.1f} seconds")

                raw_response = response["message"]["content"]

                extracted = clean_json_response(raw_response)

                if extracted is None:

                    print("\nWARNING: Could not parse Qwen JSON.")
                    print("Raw Qwen response:")
                    print(raw_response)

                    extracted = []

                elif not isinstance(extracted, list):

                    print("\nWARNING: Qwen returned non-list JSON.")
                    print(raw_response)

                    extracted = []

            except Exception as e:

                print("\nERROR while calling Ollama:")
                print(str(e))

                extracted = []

        # ----------------------------------------------------
        # Validate and normalize
        # ----------------------------------------------------

        extracted = normalize_requirements(extracted)

        print("\nQWEN OUTPUT:")

        print(
            json.dumps(
                extracted,
                indent=2,
                ensure_ascii=False
            )
        )

        print(f"\nRequirements extracted: {len(extracted)}")

        # ----------------------------------------------------
        # Add metadata
        # ----------------------------------------------------

        for requirement in extracted:

            requirement["_context_id"] = context_id

            if page_number is not None:
                requirement["_page"] = page_number

        # ----------------------------------------------------
        # Save checkpoint after every context
        # ----------------------------------------------------

        existing_output.extend(extracted)

        # IMPORTANT:
        # Even [] means this context has been processed.
        #
        # We therefore store a lightweight checkpoint marker.
        #
        # This prevents the script from repeatedly processing a context
        # that legitimately contains no requirements.
        checkpoint_marker = {
            "_context_id": context_id,
            "_processed": True,
            "_requirements_count": len(extracted)
        }

        existing_output.append(checkpoint_marker)

        save_json(OUTPUT_PATH, existing_output)

        total_new_requirements += len(extracted)

        print(f"\nSaved: {OUTPUT_PATH}")
        print(
            f"Total requirements so far: "
            f"{sum(1 for x in existing_output if isinstance(x, dict) and x.get('requirement'))}"
        )

        print("\n" + "=" * 70)

    # ========================================================
    # FINAL CLEANUP
    # ========================================================

    # Remove checkpoint-only objects from the user-facing output.
    #
    # However, we need checkpoint information for future runs.
    # Therefore create a separate checkpoint file.

    final_requirements = [
        item
        for item in existing_output
        if isinstance(item, dict)
        and item.get("requirement")
    ]

    checkpoint_ids = [
        item["_context_id"]
        for item in existing_output
        if isinstance(item, dict)
        and item.get("_processed") is True
        and item.get("_context_id")
    ]

    # Save clean requirement file.
    save_json(
        OUTPUT_PATH,
        final_requirements
    )

    # Save checkpoint separately.
    checkpoint_path = "extracted/requirements_checkpoint.json"

    save_json(
        checkpoint_path,
        checkpoint_ids
    )

    print("\n")
    print("=" * 70)
    print("EXTRACTION COMPLETED")
    print("=" * 70)

    print(f"Total contexts: {len(contexts)}")
    print(f"Contexts processed this run: {processed_count}")
    print(f"New requirements this run: {total_new_requirements}")
    print(f"Total requirements: {len(final_requirements)}")

    print(f"Output: {OUTPUT_PATH}")
    print(f"Checkpoint: {checkpoint_path}")

    print("=" * 70)


if __name__ == "__main__":
    main()