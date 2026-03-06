import json

import pytest
from unittest.mock import AsyncMock

from agent.parser import _extract_json_array, parse_menu
from models.menu import ParsedMenu


# --- _extract_json_array ---

def test_extract_direct_json_array():
    data = [{"name": "Pizza", "description": "", "category": "Mains", "tags": [], "ingredients": []}]
    assert _extract_json_array(json.dumps(data)) == data


def test_extract_array_with_preamble():
    data = [{"name": "Pizza", "description": "", "category": "Mains", "tags": [], "ingredients": []}]
    text = f"Here are the items:\n{json.dumps(data)}"
    assert _extract_json_array(text) == data


def test_extract_returns_empty_on_garbage():
    assert _extract_json_array("not json at all") == []


def test_extract_returns_empty_on_empty_string():
    assert _extract_json_array("") == []


# --- parse_menu ---

@pytest.mark.asyncio
async def test_parse_menu_happy_path():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = json.dumps([
        {
            "name": "Paneer Tikka",
            "description": "Grilled paneer",
            "category": "Mains",
            "tags": ["vegetarian"],
            "ingredients": ["paneer", "spices"],
        }
    ])

    menu = await parse_menu("some menu text", "https://example.com", mock_llm)

    assert isinstance(menu, ParsedMenu)
    assert len(menu.items) == 1
    assert menu.items[0].name == "Paneer Tikka"
    assert menu.raw_confidence == 0.8


@pytest.mark.asyncio
async def test_parse_menu_empty_llm_response():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "[]"

    menu = await parse_menu("gibberish content", "https://example.com", mock_llm)

    assert menu.items == []
    assert menu.raw_confidence == 0.0


@pytest.mark.asyncio
async def test_parse_menu_malformed_llm_response():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "I cannot parse this menu."

    menu = await parse_menu("some content", "https://example.com", mock_llm)

    assert menu.items == []


@pytest.mark.asyncio
async def test_parse_menu_skips_malformed_items():
    mock_llm = AsyncMock()
    # One valid item, one missing required "name" field
    mock_llm.complete.return_value = json.dumps([
        {"name": "Dahl", "tags": ["vegan"], "ingredients": ["lentils"]},
        {"description": "No name here"},  # missing name — should be skipped
    ])

    menu = await parse_menu("menu text", "https://example.com", mock_llm)

    assert len(menu.items) == 1
    assert menu.items[0].name == "Dahl"
