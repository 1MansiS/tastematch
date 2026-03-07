import io
import pytest
from unittest.mock import MagicMock, patch

from tools.pdf_extract import extract_text_from_pdf, _MIN_TEXT_CHARS


def _make_pdf_bytes(pages: list[str]) -> bytes:
    """Build a minimal fake PDF bytes object with mocked pypdf."""
    # We can't easily create real PDFs in tests, so we mock at the pypdf level.
    raise NotImplementedError("Use patch instead — see test helpers below")


def _mock_pypdf(page_texts: list[str]):
    """Return a context manager that patches pypdf.PdfReader."""
    mock_page = lambda text: MagicMock(extract_text=MagicMock(return_value=text))
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page(t) for t in page_texts]

    import unittest.mock
    return unittest.mock.patch("tools.pdf_extract.pypdf", create=True), mock_reader


# --- happy path ---

def test_good_text_pdf_returns_high_confidence():
    long_text = "Margherita Pizza: tomato, mozzarella, basil. " * 10  # well above threshold

    with patch("tools.pdf_extract.pypdf") as mock_pypdf:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = long_text
        mock_pypdf.PdfReader.return_value.pages = [mock_page]

        text, confidence = extract_text_from_pdf(b"fake-pdf-bytes")

    assert long_text in text
    assert confidence == 0.85


def test_multi_page_text_is_joined():
    with patch("tools.pdf_extract.pypdf") as mock_pypdf:
        pages = []
        for t in ["Page one menu items here.", "Page two more items here."]:
            p = MagicMock()
            p.extract_text.return_value = t
            pages.append(p)
        mock_pypdf.PdfReader.return_value.pages = pages

        text, _ = extract_text_from_pdf(b"fake-pdf-bytes")

    assert "Page one" in text
    assert "Page two" in text


# --- sparse / scanned ---

def test_sparse_text_returns_low_confidence():
    sparse = "Menu"  # below _MIN_TEXT_CHARS but non-empty

    with patch("tools.pdf_extract.pypdf") as mock_pypdf:
        p = MagicMock()
        p.extract_text.return_value = sparse
        mock_pypdf.PdfReader.return_value.pages = [p]

        text, confidence = extract_text_from_pdf(b"fake-pdf-bytes")

    assert text.strip() == sparse
    assert confidence == 0.40


def test_empty_text_returns_zero_confidence():
    with patch("tools.pdf_extract.pypdf") as mock_pypdf:
        p = MagicMock()
        p.extract_text.return_value = ""
        mock_pypdf.PdfReader.return_value.pages = [p]

        text, confidence = extract_text_from_pdf(b"fake-pdf-bytes")

    assert text == ""
    assert confidence == 0.0


def test_none_page_text_handled():
    """Pages returning None from extract_text should not crash."""
    with patch("tools.pdf_extract.pypdf") as mock_pypdf:
        p = MagicMock()
        p.extract_text.return_value = None
        mock_pypdf.PdfReader.return_value.pages = [p]

        text, confidence = extract_text_from_pdf(b"fake-pdf-bytes")

    assert confidence == 0.0


# --- edge case ---

def test_missing_pypdf_raises_import_error():
    import sys
    with patch.dict(sys.modules, {"pypdf": None}):
        # Re-import to trigger the ImportError path
        import importlib
        import tools.pdf_extract as pdf_mod
        importlib.reload(pdf_mod)

        with pytest.raises(ImportError, match="pypdf is required"):
            pdf_mod.extract_text_from_pdf(b"data")
