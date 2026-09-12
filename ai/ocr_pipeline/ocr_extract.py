import json
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

from ocr_engine import extract_with_ocr


BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "data" / "input"
OUTPUT_DIR = BASE_DIR / "data" / "output"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def extract_pdf(pdf_path):

    pdf_name = pdf_path.name

    output_path = (
        OUTPUT_DIR /
        f"{pdf_path.stem}_ocr_extraction.json"
    )

    pages = []

    with pdfplumber.open(pdf_path) as plumber_pdf:

        pdfium_pdf = pdfium.PdfDocument(
            str(pdf_path)
        )

        print(
            f"\nProcessing: {pdf_name}"
        )

        print(
            f"Pages: {len(plumber_pdf.pages)}"
        )

        for page_number, page in enumerate(
            plumber_pdf.pages,
            start=1
        ):

            print(
                f"\nPage {page_number}"
            )

            # -----------------------------------------
            # STEP 1
            # PDFPlumber extraction
            # -----------------------------------------

            text = (
                page.extract_text() or ""
            ).strip()

            tables = page.extract_tables()

            # -----------------------------------------
            # STEP 2
            # STRICT OCR DECISION
            # -----------------------------------------

            if text:

                extraction_method = (
                    "pdfplumber"
                )

                ocr_used = False
                ocr_confidence = None

                print(
                    "  PDFPlumber extracted text."
                )

                print(
                    "  OCR skipped."
                )

            else:

                print(
                    "  PDFPlumber extracted "
                    "no text."
                )

                print(
                    "  Running OCR..."
                )

                ocr_result = extract_with_ocr(
                    pdfium_pdf,
                    page_number
                )

                text = ocr_result["text"]

                extraction_method = "ocr"
                ocr_used = True
                ocr_confidence = (
                    ocr_result[
                        "ocr_confidence"
                    ]
                )

                print(
                    "  OCR completed."
                )

                print(
                    "  Confidence:",
                    ocr_confidence
                )

            # -----------------------------------------
            # STEP 3
            # PAGE JSON
            # -----------------------------------------

            page_data = {

                "page": page_number,

                "text": text,

                "tables": tables,

                "extraction_method":
                    extraction_method,

                "ocr_used":
                    ocr_used,

                "ocr_confidence":
                    ocr_confidence
            }

            pages.append(
                page_data
            )

        pdfium_pdf.close()

    # ---------------------------------------------
    # STEP 4
    # SAVE NEW JSON
    # ---------------------------------------------

    result = {

        "source_file":
            pdf_name,

        "pipeline":
            "PDFPlumber-first OCR fallback",

        "ocr_policy":
            "OCR is used only when PDFPlumber "
            "extracts no text from a page.",

        "pages":
            pages
    }

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(
        "\nExtraction completed."
    )

    print(
        "Saved to:",
        output_path
    )


def main():

    pdf_files = list(
        INPUT_DIR.glob("*.pdf")
    )

    if not pdf_files:

        print(
            "No PDF files found in:"
        )

        print(INPUT_DIR)

        return

    for pdf_path in pdf_files:

        extract_pdf(pdf_path)


if __name__ == "__main__":
    main()