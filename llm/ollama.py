import base64

import httpx

from llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, text_model: str, vision_model: str, base_url: str) -> None:
        self.text_model = text_model
        self.vision_model = vision_model
        self.base_url = base_url.rstrip("/")

    async def complete(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.text_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def vision(self, prompt: str, image: bytes) -> str:
        image_b64 = base64.b64encode(image).decode()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_b64],
                        }
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
