import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agent.router import InputType, classify_input
from agent.retrieval import retrieve_menu_content


# --- router tests ---

def test_classify_https_url():
    assert classify_input("https://example.com/menu") == InputType.URL


def test_classify_http_url():
    assert classify_input("http://example.com") == InputType.URL


def test_classify_jpg_is_image():
    assert classify_input("menu.jpg") == InputType.IMAGE


def test_classify_png_is_image():
    assert classify_input("menu.png") == InputType.IMAGE


def test_classify_webp_is_image():
    assert classify_input("/path/to/menu.webp") == InputType.IMAGE


def test_classify_pdf_is_pdf():
    assert classify_input("menu.pdf") == InputType.PDF


def test_classify_pdf_url_is_pdf():
    assert classify_input("https://example.com/files/menu.pdf") == InputType.PDF


def test_classify_pdf_url_with_query_is_pdf():
    assert classify_input("https://example.com/menu.pdf?v=2") == InputType.PDF


def test_classify_name_is_unknown():
    assert classify_input("Dishoom London") == InputType.UNKNOWN


def test_classify_empty_is_unknown():
    assert classify_input("") == InputType.UNKNOWN


# --- retrieval tests ---

@pytest.mark.asyncio
async def test_retrieve_url_json_ld_gives_high_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Menu content here", "https://example.com/menu", "json_ld")
        content, url, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )

    assert content == "Menu content here"
    assert url == "https://example.com/menu"
    assert confidence == 1.0


@pytest.mark.asyncio
async def test_retrieve_url_nextjs_rsc_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Menu content here", "https://example.com/menu", "nextjs_rsc")
        _, _, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )
    assert confidence == 0.95


@pytest.mark.asyncio
async def test_retrieve_url_playwright_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Menu content here", "https://example.com/menu", "playwright")
        _, _, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )
    assert confidence == 0.75


@pytest.mark.asyncio
async def test_retrieve_url_beautifulsoup_gives_lower_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Some text", "https://example.com/menu", "beautifulsoup")
        _, _, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )
    assert confidence == 0.50


@pytest.mark.asyncio
async def test_retrieve_url_empty_content_gives_zero_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("", "https://example.com/menu", "beautifulsoup")
        content, url, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )

    assert content == ""
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_retrieve_unsupported_type_raises():
    with pytest.raises(ValueError, match="Unsupported input type"):
        await retrieve_menu_content("Dishoom London", InputType.UNKNOWN)


# --- image retrieval ---

@pytest.mark.asyncio
async def test_retrieve_image_calls_vision_ocr(tmp_path):
    img_file = tmp_path / "menu.jpg"
    img_file.write_bytes(b"fake-image-data")

    llm = MagicMock()
    with patch(
        "agent.retrieval.extract_text_from_image", new_callable=AsyncMock
    ) as mock_ocr:
        mock_ocr.return_value = ("Pizza Margherita [$14]", 0.85)
        content, source, confidence = await retrieve_menu_content(
            str(img_file), InputType.IMAGE, llm
        )

    assert content == "Pizza Margherita [$14]"
    assert confidence == 0.85
    assert source == str(img_file)
    mock_ocr.assert_called_once_with(b"fake-image-data", str(img_file), llm)


@pytest.mark.asyncio
async def test_retrieve_image_without_llm_raises():
    with pytest.raises(ValueError, match="LLM provider is required"):
        await retrieve_menu_content("menu.jpg", InputType.IMAGE, llm=None)


# --- PDF retrieval ---

@pytest.mark.asyncio
async def test_retrieve_pdf_calls_pdf_extract(tmp_path):
    pdf_file = tmp_path / "menu.pdf"
    pdf_file.write_bytes(b"fake-pdf-data")

    with patch("agent.retrieval.extract_text_from_pdf") as mock_pdf:
        mock_pdf.return_value = ("Pasta Carbonara [$18]", 0.85)
        content, source, confidence = await retrieve_menu_content(
            str(pdf_file), InputType.PDF
        )

    assert content == "Pasta Carbonara [$18]"
    assert confidence == 0.85
    assert source == str(pdf_file)
    mock_pdf.assert_called_once_with(b"fake-pdf-data")


@pytest.mark.asyncio
async def test_retrieve_pdf_url_downloads_and_extracts():
    mock_response = MagicMock()
    mock_response.content = b"fake-pdf-bytes"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("agent.retrieval.extract_text_from_pdf") as mock_pdf, \
         patch("agent.retrieval.httpx.AsyncClient", return_value=mock_client):
        mock_pdf.return_value = ("Pasta Carbonara [$18]", 0.85)
        content, source, confidence = await retrieve_menu_content(
            "https://example.com/menu.pdf", InputType.PDF
        )

    assert content == "Pasta Carbonara [$18]"
    assert confidence == 0.85
    assert source == "https://example.com/menu.pdf"
    mock_pdf.assert_called_once_with(b"fake-pdf-bytes")


@pytest.mark.asyncio
async def test_retrieve_pdf_empty_gives_zero_confidence(tmp_path):
    pdf_file = tmp_path / "menu.pdf"
    pdf_file.write_bytes(b"fake-pdf-data")

    with patch("agent.retrieval.extract_text_from_pdf") as mock_pdf:
        mock_pdf.return_value = ("", 0.0)
        content, source, confidence = await retrieve_menu_content(
            str(pdf_file), InputType.PDF
        )

    assert content == ""
    assert confidence == 0.0
