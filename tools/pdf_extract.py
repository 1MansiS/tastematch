import io

try:
    import pypdf
except ImportError:
    pypdf = None  # type: ignore[assignment]

_MIN_TEXT_CHARS = 100  # below this threshold text is considered sparse (likely scanned)


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, float]:
    """Extract text from a PDF file.

    Returns (text, confidence):
      - confidence 0.85 — good text-based PDF with sufficient content
      - confidence 0.40 — sparse text, possibly a scanned PDF
      - confidence 0.0  — no text at all (scanned PDF; vision not yet supported)

    Raises ImportError if pypdf is not installed.
    """
    if pypdf is None:
        raise ImportError(
            "pypdf is required for PDF extraction. Install it with: pip install pypdf"
        )

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")

    full_text = "\n".join(pages)
    stripped = full_text.strip()

    if len(stripped) >= _MIN_TEXT_CHARS:
        return full_text, 0.85
    elif stripped:
        return full_text, 0.40
    else:
        return "", 0.0
