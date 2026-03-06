from agent.router import InputType
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
    user_input: str, input_type: InputType
) -> tuple[str, str, float]:
    """Return (content, source_url, confidence).

    confidence is 0.0–1.0 reflecting how likely the content contains a full menu.
    """
    if input_type == InputType.URL:
        content, final_url, method = await fetch_and_clean(user_input)
        confidence = _METHOD_CONFIDENCE.get(method, 0.5) if content else 0.0
        return content, final_url, confidence

    raise ValueError(f"Unsupported input type: {input_type!r}")
