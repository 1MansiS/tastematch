import pytest
from unittest.mock import AsyncMock, patch

from agent.router import InputType, classify_input
from agent.retrieval import retrieve_menu_content


# --- router tests ---

def test_classify_https_url():
    assert classify_input("https://example.com/menu") == InputType.URL


def test_classify_http_url():
    assert classify_input("http://example.com") == InputType.URL


def test_classify_name_is_unknown():
    assert classify_input("Dishoom London") == InputType.UNKNOWN


def test_classify_empty_is_unknown():
    assert classify_input("") == InputType.UNKNOWN


# --- retrieval tests ---

@pytest.mark.asyncio
async def test_retrieve_url_json_ld_gives_high_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Menu content here", "https://example.com/menu", "json_ld")
        content, url, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )

    assert content == "Menu content here"
    assert url == "https://example.com/menu"
    assert confidence == 1.0


@pytest.mark.asyncio
async def test_retrieve_url_nextjs_rsc_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Menu content here", "https://example.com/menu", "nextjs_rsc")
        _, _, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )
    assert confidence == 0.95


@pytest.mark.asyncio
async def test_retrieve_url_playwright_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Menu content here", "https://example.com/menu", "playwright")
        _, _, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )
    assert confidence == 0.75


@pytest.mark.asyncio
async def test_retrieve_url_beautifulsoup_gives_lower_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("Some text", "https://example.com/menu", "beautifulsoup")
        _, _, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )
    assert confidence == 0.50


@pytest.mark.asyncio
async def test_retrieve_url_empty_content_gives_zero_confidence():
    with patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ("", "https://example.com/menu", "beautifulsoup")
        content, url, confidence = await retrieve_menu_content(
            "https://example.com/menu", InputType.URL
        )

    assert content == ""
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_retrieve_unsupported_type_raises():
    with pytest.raises(ValueError, match="Unsupported input type"):
        await retrieve_menu_content("Dishoom London", InputType.UNKNOWN)
