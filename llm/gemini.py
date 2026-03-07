import asyncio
import base64
import os

import httpx

from llm.base import LLMProvider

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


async def _post_with_retry(client: httpx.AsyncClient, url: str, json: dict) -> httpx.Response:
    """POST with exponential backoff on transient / rate-limit errors."""
    for attempt in range(_MAX_RETRIES):
        response = await client.post(url, json=json)
        if response.status_code not in _RETRYABLE_STATUS:
            response.raise_for_status()
            return response
        if attempt == _MAX_RETRIES - 1:
            response.raise_for_status()
        await asyncio.sleep(2 ** attempt)  # 1s, 2s
    raise RuntimeError("Retry loop exited unexpectedly")


class GeminiProvider(LLMProvider):
    def __init__(self, text_model: str, vision_model: str) -> None:
        self.text_model = text_model
        self.vision_model = vision_model
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY environment variable is not set")
        self._api_key = api_key

    async def complete(self, prompt: str) -> str:
        url = f"{_BASE_URL}/{self.text_model}:generateContent?key={self._api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await _post_with_retry(
                client, url, json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def vision(self, prompt: str, image: bytes, mime_type: str = "image/jpeg") -> str:
        image_b64 = base64.b64encode(image).decode()
        url = f"{_BASE_URL}/{self.vision_model}:generateContent?key={self._api_key}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await _post_with_retry(
                client,
                url,
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": image_b64,
                                    }
                                },
                            ]
                        }
                    ]
                },
            )
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
