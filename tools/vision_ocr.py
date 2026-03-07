from pathlib import Path

from llm.base import LLMProvider

_VISION_PROMPT = """\
You are a menu extraction assistant. The image shows a restaurant or coffee shop menu.

Extract ALL visible menu items from the image. For each item include the name, \
description (if visible), and price (if visible).

Return plain text — one item per line, like:
  Margherita Pizza: tomato, mozzarella, basil [$14]
  Caesar Salad: romaine, parmesan, croutons [$11]

Include every item you can see. If no menu items are visible, return an empty string.
"""

_MIME_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_MIME_TYPES)


async def extract_text_from_image(
    image_bytes: bytes, file_path: str, llm: LLMProvider
) -> tuple[str, float]:
    """Extract menu text from an image using LLM vision.

    Returns (text, confidence). Confidence is 0.85 on success, 0.0 if no text extracted.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in _MIME_TYPES:
        raise ValueError(
            f"Unsupported image format: {ext!r}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    mime_type = _MIME_TYPES[ext]
    text = await llm.vision(_VISION_PROMPT, image_bytes, mime_type)
    confidence = 0.85 if text.strip() else 0.0
    return text, confidence
