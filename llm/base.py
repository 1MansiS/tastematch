from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str) -> str: ...

    @abstractmethod
    async def vision(self, prompt: str, image: bytes) -> str: ...
