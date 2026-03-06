import json

import pytest
from unittest.mock import AsyncMock

from agent.matcher import match_profile
from models.menu import MenuItem, ParsedMenu
from models.profile import FoodProfile


def _make_menu() -> ParsedMenu:
    return ParsedMenu(
        items=[
            MenuItem(
                name="Lentil Dahl",
                description="Rich lentil curry",
                category="Mains",
                tags=["vegetarian", "vegan"],
                ingredients=["lentils", "spices"],
            ),
            MenuItem(
                name="Paneer Tikka",
                description="Grilled paneer",
                category="Mains",
                tags=["vegetarian"],
                ingredients=["paneer"],
            ),
            MenuItem(
                name="Chicken Curry",
                description="Slow-cooked chicken",
                category="Mains",
                tags=[],
                ingredients=["chicken"],
            ),
        ],
        source_url="https://example.com",
        raw_confidence=0.8,
    )


def _make_profile() -> FoodProfile:
    return FoodProfile(
        diet_type="vegetarian",
        loved_ingredients=["lentils", "paneer"],
        avoid_ingredients=["eggs"],
        must_have=[],
        nice_to_have=["high protein"],
        avoid_vibes=[],
        allergens=[],
        intolerances=[],
    )


@pytest.mark.asyncio
async def test_match_happy_path():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = json.dumps({
        "match_score": 75,
        "match_label": "Good match",
        "matching_items": 2,
        "best_picks": ["Lentil Dahl", "Paneer Tikka"],
        "warnings": ["1 non-vegetarian dish on menu"],
    })

    result = await match_profile(_make_menu(), _make_profile(), mock_llm)

    assert result["match_score"] == 75
    assert "Lentil Dahl" in result["best_picks"]
    assert len(result["warnings"]) == 1


@pytest.mark.asyncio
async def test_match_fallback_on_unparseable_response():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Unable to analyze the menu."

    result = await match_profile(_make_menu(), _make_profile(), mock_llm)

    assert "match_score" in result
    assert result["match_score"] == 50  # fallback default
    assert "warnings" in result


@pytest.mark.asyncio
async def test_match_extracts_json_from_noisy_response():
    mock_llm = AsyncMock()
    payload = {
        "match_score": 60,
        "match_label": "Good match",
        "matching_items": 2,
        "best_picks": ["Lentil Dahl"],
        "warnings": [],
    }
    mock_llm.complete.return_value = f"Sure! Here is the result:\n{json.dumps(payload)}"

    result = await match_profile(_make_menu(), _make_profile(), mock_llm)

    assert result["match_score"] == 60


@pytest.mark.asyncio
async def test_match_returns_warnings_list():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = json.dumps({
        "match_score": 30,
        "match_label": "Poor match",
        "matching_items": 0,
        "best_picks": [],
        "warnings": ["Diet not respected", "Allergen present"],
    })

    result = await match_profile(_make_menu(), _make_profile(), mock_llm)

    assert len(result["warnings"]) == 2
