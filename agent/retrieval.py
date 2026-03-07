from pathlib import Path

import httpx

from agent.router import InputType
from llm.base import LLMProvider
from tools.pdf_extract import extract_text_from_pdf
from tools.vision_ocr import extract_text_from_image
from tools.web_fetch import fetch_and_clean

# Confidence by extraction method — higher = more structured/reliable data
_METHOD_CONFIDENCE: dict[str, float] = {
    "json_ld": 1.0,
    "nextjs_rsc": 0.95,
    "next_data": 0.90,
    "trafilatura": 0.70,
    "playwright": 0.75,
    "beautifulsoup": 0.50,
}


async def retrieve_menu_content(
    user_input: str, input_type: InputType, llm: LLMProvider | None = None
) -> tuple[str, str, float]:
    """Return (content, source, confidence).

    confidence is 0.0–1.0 reflecting how likely the content contains a full menu.
    llm is required when input_type is IMAGE.
    """
    if input_type == InputType.URL:
        content, final_url, method = await fetch_and_clean(user_input)
        confidence = _METHOD_CONFIDENCE.get(method, 0.5) if content else 0.0
        return content, final_url, confidence

    if input_type == InputType.IMAGE:
        if llm is None:
            raise ValueError("An LLM provider is required for image input")
        image_bytes = Path(user_input).read_bytes()
        text, confidence = await extract_text_from_image(image_bytes, user_input, llm)
        return text, user_input, confidence

    if input_type == InputType.PDF:
        if user_input.startswith(("http://", "https://")):
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(user_input)
                response.raise_for_status()
                pdf_bytes = response.content
        else:
            pdf_bytes = Path(user_input).read_bytes()
        text, confidence = extract_text_from_pdf(pdf_bytes)
        return text, user_input, confidence

    raise ValueError(f"Unsupported input type: {input_type!r}")
