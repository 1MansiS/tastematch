from typing import Optional
from pydantic import BaseModel


class MenuItem(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = []
    ingredients: list[str] = []


class ParsedMenu(BaseModel):
    items: list[MenuItem]
    source_url: str
    raw_confidence: float  # 0.0–1.0, how complete we think the menu is
