import pytest
from unittest.mock import AsyncMock, MagicMock

from tools.vision_ocr import extract_text_from_image, SUPPORTED_EXTENSIONS


def _mock_llm(vision_return: str) -> MagicMock:
    llm = MagicMock()
    llm.vision = AsyncMock(return_value=vision_return)
    return llm


# --- happy path ---

@pytest.mark.asyncio
async def test_extract_jpeg_returns_text_and_confidence():
    llm = _mock_llm("Margherita Pizza: tomato, mozzarella [$14]")
    text, confidence = await extract_text_from_image(b"fake-bytes", "menu.jpg", llm)

    assert "Margherita" in text
    assert confidence == 0.85


@pytest.mark.asyncio
async def test_extract_png_passes_correct_mime_type():
    llm = _mock_llm("Caesar Salad [$11]")
    await extract_text_from_image(b"fake-bytes", "menu.png", llm)

    llm.vision.assert_called_once()
    _, _, mime = llm.vision.call_args.args
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_extract_webp_passes_correct_mime_type():
    llm = _mock_llm("Burger [$12]")
    await extract_text_from_image(b"fake-bytes", "menu.webp", llm)

    _, _, mime = llm.vision.call_args.args
    assert mime == "image/webp"


@pytest.mark.asyncio
async def test_extract_jpeg_extension_passes_jpeg_mime():
    llm = _mock_llm("Pasta [$15]")
    await extract_text_from_image(b"fake-bytes", "menu.jpeg", llm)

    _, _, mime = llm.vision.call_args.args
    assert mime == "image/jpeg"


# --- empty / failure ---

@pytest.mark.asyncio
async def test_empty_vision_response_gives_zero_confidence():
    llm = _mock_llm("")
    text, confidence = await extract_text_from_image(b"fake-bytes", "menu.jpg", llm)

    assert text == ""
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_whitespace_only_response_gives_zero_confidence():
    llm = _mock_llm("   \n  ")
    _, confidence = await extract_text_from_image(b"fake-bytes", "menu.jpg", llm)
    assert confidence == 0.0


# --- edge cases ---

@pytest.mark.asyncio
async def test_unsupported_extension_raises():
    llm = _mock_llm("anything")
    with pytest.raises(ValueError, match="Unsupported image format"):
        await extract_text_from_image(b"fake-bytes", "menu.bmp", llm)


@pytest.mark.asyncio
async def test_unsupported_tiff_raises():
    llm = _mock_llm("anything")
    with pytest.raises(ValueError, match="Unsupported image format"):
        await extract_text_from_image(b"fake-bytes", "scan.tiff", llm)


def test_supported_extensions_set():
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".png" in SUPPORTED_EXTENSIONS
    assert ".webp" in SUPPORTED_EXTENSIONS
    assert ".bmp" not in SUPPORTED_EXTENSIONS
