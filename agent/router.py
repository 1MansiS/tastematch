from enum import Enum


class InputType(str, Enum):
    URL = "url"
    UNKNOWN = "unknown"


def classify_input(user_input: str) -> InputType:
    stripped = user_input.strip()
    if stripped.startswith(("http://", "https://")):
        return InputType.URL
    return InputType.UNKNOWN
