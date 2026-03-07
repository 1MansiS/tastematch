from enum import Enum
from pathlib import Path

_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


class InputType(str, Enum):
    URL = "url"
    IMAGE = "image"
    PDF = "pdf"
    UNKNOWN = "unknown"


def classify_input(user_input: str) -> InputType:
    stripped = user_input.strip()
    if stripped.startswith(("http://", "https://")):
        path_part = stripped.split("?")[0].split("#")[0]
        if path_part.lower().endswith(".pdf"):
            return InputType.PDF
        return InputType.URL
    ext = Path(stripped).suffix.lower()
    if ext in _IMAGE_EXTENSIONS:
        return InputType.IMAGE
    if ext == ".pdf":
        return InputType.PDF
    return InputType.UNKNOWN
