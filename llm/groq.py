import asyncio
import base64
import os

import httpx

from llm.base import LLMProvider

_BASE_URL = "https://api.groq.com/openai/v1"
_RETRY_DELAYS = [5, 15, 30]  # seconds between retries on 429


class GroqProvider(LLMProvider):
    def __init__(self, text_model: str, vision_model: str) -> None:
        self.text_model = text_model
        self.vision_model = vision_model
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY environment variable is not set")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def _post_with_retry(self, client: httpx.AsyncClient, url: str, payload: dict) -> dict:
        for attempt, delay in enumerate([0] + _RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            response = await client.post(url, headers=self._headers, json=payload)
            if response.status_code == 429 and attempt < len(_RETRY_DELAYS):
                retry_after = int(response.headers.get("retry-after", delay or 5))
                await asyncio.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()  # re-raise after exhausting retries

    async def complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            data = await self._post_with_retry(
                client,
                f"{_BASE_URL}/chat/completions",
                {
                    "model": self.text_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            return data["choices"][0]["message"]["content"]

    async def vision(self, prompt: str, image: bytes, mime_type: str = "image/jpeg") -> str:
        image_b64 = base64.b64encode(image).decode()
        async with httpx.AsyncClient(timeout=60.0) as client:
            data = await self._post_with_retry(
                client,
                f"{_BASE_URL}/chat/completions",
                {
                    "model": self.vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_b64}"
                                    },
                                },
                            ],
                        }
                    ],
                },
            )
            return data["choices"][0]["message"]["content"]
