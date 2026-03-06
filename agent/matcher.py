import json
import re

from llm.base import LLMProvider
from models.menu import ParsedMenu
from models.profile import FoodProfile

_MATCH_PROMPT = """\
You are a menu matching assistant. Score how well this venue suits the user's food profile.

Food Profile:
{profile}

Menu Items ({item_count} total):
{items}

Return a JSON object with this exact structure:
{{
  "match_score": <integer 0-100>,
  "match_label": "<Strong match|Good match|Decent match|Poor match>",
  "matching_items": <count of items that fit the profile>,
  "best_picks": ["item1", "item2", "item3"],
  "warnings": ["warning1", "warning2"]
}}

Scoring guidelines:
- 80-100: Strong match — many loved items, diet respected, good variety
- 60-79: Good match — diet respected, some preferred items present
- 40-59: Decent match — diet mostly respected, limited options
- 0-39:  Poor match — diet violated, allergens present, or very few options

Return ONLY the JSON object — no explanation, no markdown fences.
"""

_FALLBACK_RESULT: dict = {
    "match_score": 50,
    "match_label": "Decent match",
    "matching_items": 0,
    "best_picks": [],
    "warnings": ["Could not fully analyze menu"],
}


def _items_summary(menu: ParsedMenu) -> str:
    lines = []
    for item in menu.items[:50]:  # cap to avoid blowing the context
        line = f"- {item.name}"
        if item.description:
            line += f": {item.description}"
        if item.tags:
            line += f" [{', '.join(item.tags)}]"
        if item.ingredients:
            line += f" (ingredients: {', '.join(item.ingredients[:5])})"
        lines.append(line)
    return "\n".join(lines)


async def match_profile(
    menu: ParsedMenu, profile: FoodProfile, llm: LLMProvider
) -> dict:
    prompt = _MATCH_PROMPT.format(
        profile=json.dumps(profile.model_dump(), indent=2),
        item_count=len(menu.items),
        items=_items_summary(menu),
    )
    raw = await llm.complete(prompt)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return dict(_FALLBACK_RESULT)
