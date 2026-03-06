import json
from pathlib import Path

from llm.base import LLMProvider


def get_provider(config_path: str = "config.json") -> LLMProvider:
    config = json.loads(Path(config_path).read_text())
    llm_cfg = config["llm"]
    provider = llm_cfg["provider"]

    if provider == "ollama":
        from llm.ollama import OllamaProvider

        return OllamaProvider(
            text_model=llm_cfg["text_model"],
            vision_model=llm_cfg.get("vision_model", llm_cfg["text_model"]),
            base_url=llm_cfg.get("base_url", "http://localhost:11434"),
        )

    if provider == "groq":
        from llm.groq import GroqProvider

        return GroqProvider(
            text_model=llm_cfg["text_model"],
            vision_model=llm_cfg.get("vision_model", llm_cfg["text_model"]),
        )

    if provider == "gemini":
        from llm.gemini import GeminiProvider

        return GeminiProvider(
            text_model=llm_cfg["text_model"],
            vision_model=llm_cfg.get("vision_model", llm_cfg["text_model"]),
        )

    raise ValueError(f"Unsupported provider: {provider!r}")
