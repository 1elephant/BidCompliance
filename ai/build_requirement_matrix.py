import json
import os


# ============================================================
# PATHS
# ============================================================

INPUT_PATH = "extracted/requirements.json"
OUTPUT_PATH = "extracted/requirement_matrix.json"


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


# ============================================================
# BUILD MATRIX
# ============================================================

def build_requirement_matrix(requirements):

    matrix = []

    for req in requirements:

        requirement_id = req["requirement_id"]

        requirement = {
            "requirement_id": requirement_id,

            "category": req["category"],

            "requirement": req["requirement"],

            "requirement_type": req["requirement_type"],

            "source": {
                "pages": [],
                "contexts": []
            },

            "rag": {
                "query": req["requirement"],
                "retrieved_evidence": []
            },

            "compliance": {
                "status": "NOT_EVALUATED",
                "evidence": [],
                "remarks": ""
            }
        }

        # ----------------------------------------------------
        # Preserve source information
        # ----------------------------------------------------

        for source in req.get("sources", []):

            page = source.get("page")
            context_id = source.get("context_id")

            if page is not None and page not in requirement["source"]["pages"]:
                requirement["source"]["pages"].append(page)

            if (
                context_id is not None
                and context_id not in requirement["source"]["contexts"]
            ):
                requirement["source"]["contexts"].append(context_id)

        matrix.append(requirement)

    return matrix


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BUILDING REQUIREMENT MATRIX")
    print("=" * 70)

    print(f"Input : {INPUT_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print()

    requirements = load_json(INPUT_PATH)

    if not isinstance(requirements, list):
        raise ValueError(
            "requirements.json must contain a JSON list."
        )

    print(f"Requirements found: {len(requirements)}")
    print()

    matrix = build_requirement_matrix(requirements)

    save_json(
        OUTPUT_PATH,
        matrix
    )

    print("=" * 70)
    print("REQUIREMENT MATRIX CREATED")
    print("=" * 70)

    print(f"Total requirements: {len(matrix)}")
    print()

    for req in matrix:

        print(
            f"{req['requirement_id']} | "
            f"{req['category']} | "
            f"Page(s): {req['source']['pages']}"
        )

        print(
            f"  RAG query: {req['rag']['query']}"
        )

        print(
            f"  Status: {req['compliance']['status']}"
        )

        print()

    print("=" * 70)
    print(f"Saved: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()