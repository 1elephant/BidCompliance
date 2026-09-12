import statistics

import pypdfium2 as pdfium
import pytesseract


def render_page(pdf, page_number, dpi=300):
    page = pdf[page_number - 1]

    scale = dpi / 72

    bitmap = page.render(scale=scale)

    return bitmap.to_pil()


def extract_with_ocr(
    pdf,
    page_number,
    language="eng",
    dpi=300
):
    image = render_page(
        pdf,
        page_number,
        dpi=dpi
    )

    text = pytesseract.image_to_string(
        image,
        lang=language
    ).strip()

    data = pytesseract.image_to_data(
        image,
        lang=language,
        output_type=pytesseract.Output.DICT
    )

    confidences = []

    for value in data["conf"]:
        try:
            confidence = float(value)

            if confidence >= 0:
                confidences.append(confidence)

        except (ValueError, TypeError):
            continue

    if confidences:
        average_confidence = round(
            statistics.mean(confidences),
            2
        )
    else:
        average_confidence = None

    return {
        "text": text,
        "ocr_confidence": average_confidence,
        "ocr_language": language,
        "ocr_dpi": dpi
    }