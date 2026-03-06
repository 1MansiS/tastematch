import json
import re

from llm.base import LLMProvider
from models.menu import MenuItem, ParsedMenu

_PARSE_PROMPT = """\
You are a menu parsing assistant. Extract all menu items from the text below.

Return a JSON array of objects with this exact structure:
[
  {{
    "name": "Item name",
    "description": "Item description or empty string",
    "category": "Category (Appetizers, Mains, Desserts, Drinks, etc.)",
    "tags": ["vegetarian", "vegan", "spicy", ...],
    "ingredients": ["ingredient1", "ingredient2", ...]
  }}
]

Rules:
- Only include actual menu items, not venue info, hours, or policies.
- Infer tags from the description where possible (e.g. no meat mentioned → "vegetarian").
- If you cannot find any items, return [].
- Return ONLY the JSON array — no explanation, no markdown fences.

Menu text:
{content}
"""


def _extract_json_array(text: str) -> list:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Partial recovery: response may be truncated mid-array; extract complete objects
    items = []
    for obj_match in re.finditer(r"\{[^{}]*\}", text, re.DOTALL):
        try:
            items.append(json.loads(obj_match.group()))
        except json.JSONDecodeError:
            pass
    return items


async def parse_menu(
    content: str, source_url: str, llm: LLMProvider, debug: bool = False
) -> ParsedMenu:
    from rich.console import Console
    _console = Console()

    prompt = _PARSE_PROMPT.format(content=content)
    raw = await llm.complete(prompt)

    if debug:
        _console.print(prompt)
        _console.print(f"\n[dim]--- LLM raw response ({len(raw)} chars) ---[/dim]")
        _console.print(f"[dim]{raw[:800]}[/dim]")
        if len(raw) > 800:
            _console.print(f"[dim]... (truncated) ...[/dim]")
            _console.print(f"[dim]{raw[-200:]}[/dim]")
        _console.print(f"[dim]--- end ---[/dim]\n")

    items_data = _extract_json_array(raw)
    items: list[MenuItem] = []
    for item_data in items_data:
        try:
            items.append(MenuItem(**item_data))
        except Exception:
            pass  # skip malformed entries

    if not items and not debug:
        # Always show the raw response on failure to aid diagnosis
        _console.print(f"\n[dim]LLM raw response (first 500 chars):[/dim]\n[dim]{raw[:500]}[/dim]\n")

    return ParsedMenu(
        items=items,
        source_url=source_url,
        raw_confidence=0.8 if items else 0.0,
    )
