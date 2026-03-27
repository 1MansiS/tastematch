import pytest
from unittest.mock import AsyncMock, patch

from tools.search import search_venue_menu


# --- happy path ---

def _mock_tavily(mock_response: dict) -> tuple:
    """Return context managers to patch Tavily and make it available."""
    instance = AsyncMock()
    instance.search = AsyncMock(return_value=mock_response)

    class FakeClient:
        def __new__(cls, *a, **kw):
            return instance

    return (
        patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}),
        patch("tools.search._TAVILY_AVAILABLE", True),
        patch("tools.search.AsyncTavilyClient", FakeClient),
    )


@pytest.mark.asyncio
async def test_search_returns_results():
    mock_response = {
        "results": [
            {"url": "https://dishoom.com/menus", "title": "Dishoom Menu", "content": "Indian food menu", "score": 0.95},
            {"url": "https://yelp.com/dishoom", "title": "Dishoom on Yelp", "content": "Restaurant info", "score": 0.80},
        ]
    }
    env_patch, avail_patch, client_patch = _mock_tavily(mock_response)
    with env_patch, avail_patch, client_patch:
        results = await search_venue_menu("Dishoom London")

    # yelp.com is now in _BLOCKED_DOMAINS — only the official URL should pass through
    assert len(results) == 1
    assert results[0]["url"] == "https://dishoom.com/menus"
    assert results[0]["title"] == "Dishoom Menu"
    assert results[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_search_query_appends_menu():
    """Verifies the query passed to Tavily includes 'menu'."""
    instance = AsyncMock()
    instance.search = AsyncMock(return_value={"results": []})

    class FakeClient:
        def __new__(cls, *a, **kw):
            return instance

    with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), \
         patch("tools.search._TAVILY_AVAILABLE", True), \
         patch("tools.search.AsyncTavilyClient", FakeClient):
        await search_venue_menu("Blue Bottle Coffee")

    call_kwargs = instance.search.call_args
    assert "menu" in call_kwargs.kwargs.get("query", "")


# --- failure / fallback paths ---

@pytest.mark.asyncio
async def test_search_no_api_key_returns_empty():
    with patch.dict("os.environ", {}, clear=True):
        results = await search_venue_menu("Dishoom London")
    assert results == []


@pytest.mark.asyncio
async def test_search_tavily_not_installed_returns_empty():
    with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), \
         patch("tools.search._TAVILY_AVAILABLE", False):
        results = await search_venue_menu("Dishoom London")
    assert results == []


@pytest.mark.asyncio
async def test_search_api_error_returns_empty():
    instance = AsyncMock()
    instance.search = AsyncMock(side_effect=Exception("API error"))

    class FakeClient:
        def __new__(cls, *a, **kw):
            return instance

    with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}), \
         patch("tools.search._TAVILY_AVAILABLE", True), \
         patch("tools.search.AsyncTavilyClient", FakeClient):
        results = await search_venue_menu("Dishoom London")

    assert results == []


# --- edge cases ---

@pytest.mark.asyncio
async def test_search_empty_results():
    env_patch, avail_patch, client_patch = _mock_tavily({"results": []})
    with env_patch, avail_patch, client_patch:
        results = await search_venue_menu("Unknown Venue XYZ 99999")
    assert results == []


@pytest.mark.asyncio
async def test_search_filters_gayot_and_other_guides():
    """gayot.com and similar travel/guide sites are filtered from results."""
    mock_response = {
        "results": [
            {"url": "https://www.gayot.com/restaurants/menu/dali-restaurant", "title": "Dali on Gayot", "content": "tapas", "score": 0.95},
            {"url": "https://dalirestaurant.com", "title": "Dali Restaurant", "content": "menu", "score": 0.80},
        ]
    }
    env_patch, avail_patch, client_patch = _mock_tavily(mock_response)
    with env_patch, avail_patch, client_patch:
        results = await search_venue_menu("Dalis Somerville MA")

    assert len(results) == 1
    assert results[0]["url"] == "https://dalirestaurant.com"


@pytest.mark.asyncio
async def test_search_missing_fields_handled_gracefully():
    """Items with missing fields should still be included with defaults."""
    mock_response = {
        "results": [
            {"url": "https://example.com", "score": 0.7},  # no title / content
        ]
    }
    env_patch, avail_patch, client_patch = _mock_tavily(mock_response)
    with env_patch, avail_patch, client_patch:
        results = await search_venue_menu("Some Venue")

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"
    assert results[0]["title"] == ""
    assert results[0]["content"] == ""
    assert results[0]["score"] == 0.7
