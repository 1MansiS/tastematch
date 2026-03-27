import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agent.router import InputType, classify_input
from agent.retrieval import retrieve_menu_content, _domain_matches_venue, _is_third_party


# --- router tests ---

def test_classify_https_url():
    assert classify_input("https://example.com/menu") == InputType.URL


def test_classify_http_url():
    assert classify_input("http://example.com") == InputType.URL


def test_classify_jpg_is_image():
    assert classify_input("menu.jpg") == InputType.IMAGE


def test_classify_png_is_image():
    assert classify_input("menu.png") == InputType.IMAGE


def test_classify_webp_is_image():
    assert classify_input("/path/to/menu.webp") == InputType.IMAGE


def test_classify_pdf_is_pdf():
    assert classify_input("menu.pdf") == InputType.PDF


def test_classify_pdf_url_is_pdf():
    assert classify_input("https://example.com/files/menu.pdf") == InputType.PDF


def test_classify_pdf_url_with_query_is_pdf():
    assert classify_input("https://example.com/menu.pdf?v=2") == InputType.PDF


def test_classify_name_is_name():
    assert classify_input("Dishoom London") == InputType.NAME


def test_classify_name_city_country_is_name():
    assert classify_input("Dishoom, London, UK") == InputType.NAME


def test_classify_address_is_name():
    assert classify_input("7 Boundary St, London") == InputType.NAME


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


# --- name retrieval ---

@pytest.mark.asyncio
async def test_retrieve_name_places_success():
    """Places lookup returns a website → fetch_and_clean succeeds."""
    place = {"name": "Dishoom", "website": "https://dishoom.com/menus", "address": "London", "place_id": "abc"}

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=place), \
         patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock,
               return_value=("Menu content", "https://dishoom.com/menus", "json_ld")), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=[]):
        content, source, confidence = await retrieve_menu_content("Dishoom London", InputType.NAME)

    assert content == "Menu content"
    assert source == "https://dishoom.com/menus"
    assert confidence == 1.0  # json_ld, no penalty for Places


@pytest.mark.asyncio
async def test_retrieve_name_places_weak_content_tries_menu_links():
    """Places gives beautifulsoup content without price signals → tries menu links."""
    place = {"name": "Sarma", "website": "https://sarmarestaurant.com", "address": "Somerville", "place_id": "xyz"}

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=place), \
         patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock) as mock_fetch, \
         patch("agent.retrieval.fetch_raw_html", new_callable=AsyncMock,
               return_value="<html><a href='/#dinner-menu'>Dinner Menu</a></html>"), \
         patch("agent.retrieval.find_menu_links",
               return_value=["https://sarmarestaurant.com/#dinner-menu"]), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=[]):
        mock_fetch.side_effect = [
            ("No prices here just homepage", "https://sarmarestaurant.com", "beautifulsoup"),
            ("Starters\nBraised lamb shank $28\nMeze Platter $22\nMains\nGrilled sea bass $32",
             "https://sarmarestaurant.com/#dinner-menu", "playwright"),
        ]
        content, source, confidence = await retrieve_menu_content(
            "Sarma, Somerville, MA, USA", InputType.NAME
        )

    assert "Braised lamb shank" in content
    assert source == "https://sarmarestaurant.com/#dinner-menu"
    assert confidence == 0.75  # playwright


@pytest.mark.asyncio
async def test_retrieve_name_places_strong_beautifulsoup_skips_link_discovery():
    """If beautifulsoup content already has price signals, skip menu link discovery."""
    place = {"name": "Cafe A", "website": "https://cafea.com", "address": "Boston", "place_id": "abc"}

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=place), \
         patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock,
               return_value=("Drinks\nEspresso $4.50\nLatte $6.00\nCappuccino $5.00", "https://cafea.com", "beautifulsoup")), \
         patch("agent.retrieval.fetch_raw_html", new_callable=AsyncMock) as mock_raw, \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=[]):
        content, source, confidence = await retrieve_menu_content("Cafe A, Boston", InputType.NAME)

    assert "Espresso" in content
    assert confidence == 0.50
    mock_raw.assert_not_called()  # no need to go further


@pytest.mark.asyncio
async def test_retrieve_name_tavily_filters_third_party():
    """Tavily results from third-party aggregators are skipped."""
    tavily_results = [
        {"url": "https://yelp.com/sarma", "title": "Sarma on Yelp", "content": "Great food", "score": 0.9},
        {"url": "https://tripadvisor.com/sarma", "title": "Sarma on TA", "content": "Lovely", "score": 0.8},
        {"url": "https://sarmarestaurant.com", "title": "Sarma", "content": "menu snippet", "score": 0.7},
    ]

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=None), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=tavily_results), \
         patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock,
               return_value=("Starters\nBraised lamb shank $28\nRoasted beet $18\nMains\nGrilled sea bass $32",
                             "https://sarmarestaurant.com", "trafilatura")) as mock_fetch:
        content, source, confidence = await retrieve_menu_content(
            "Sarma, Somerville, MA, USA", InputType.NAME
        )

    # Only the non-third-party URL should have been fetched
    assert mock_fetch.call_count == 1
    assert mock_fetch.call_args[0][0] == "https://sarmarestaurant.com"
    assert "Braised lamb shank" in content


@pytest.mark.asyncio
async def test_retrieve_name_tavily_official_domain_prioritised():
    """When Places returns an official domain, that Tavily result is tried first."""
    place = {"name": "Sarma", "website": "https://sarmarestaurant.com", "address": "Somerville", "place_id": "xyz"}
    tavily_results = [
        {"url": "https://eater.com/sarma-review", "title": "Eater review", "content": "Snippet", "score": 0.9},
        {"url": "https://sarmarestaurant.com/menu", "title": "Sarma Menu", "content": "menu", "score": 0.7},
    ]

    fetch_calls: list[str] = []

    async def mock_fetch(url: str):
        fetch_calls.append(url)
        if "sarmarestaurant" in url and url != "https://sarmarestaurant.com":
            return ("Lamb Shank $28", url, "trafilatura")
        # homepage → weak content triggers link discovery path
        return ("Homepage text no prices", url, "beautifulsoup")

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=place), \
         patch("agent.retrieval.fetch_and_clean", side_effect=mock_fetch), \
         patch("agent.retrieval.fetch_raw_html", new_callable=AsyncMock, return_value="<html></html>"), \
         patch("agent.retrieval.find_menu_links", return_value=[]), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=tavily_results):
        content, source, confidence = await retrieve_menu_content(
            "Sarma, Somerville, MA, USA", InputType.NAME
        )

    # Official domain Tavily result tried before eater.com
    tavily_fetch_calls = [u for u in fetch_calls if u != "https://sarmarestaurant.com"]
    assert tavily_fetch_calls[0] == "https://sarmarestaurant.com/menu"


def test_domain_matches_exact():
    assert _domain_matches_venue("https://sarmarestaurant.com", "sarma") is True


def test_domain_matches_possessive_trailing_s():
    """'Dalis' should match dalirestaurant.com via prefix stripping."""
    assert _domain_matches_venue("https://dalirestaurant.com", "dalis") is True


def test_domain_no_match_short_name():
    assert _domain_matches_venue("https://unrelated.com", "dalis") is False


def test_gayot_is_third_party():
    assert _is_third_party("https://www.gayot.com/restaurants/menu/dali") is True


def test_gayot_blocked_in_search_results():
    """gayot.com results are filtered out and never fetched."""
    from tools.search import _is_blocked
    assert _is_blocked("https://www.gayot.com/restaurants/menu/dali-restaurant") is True


@pytest.mark.asyncio
async def test_retrieve_name_gayot_skipped_prefers_official():
    """gayot.com result is filtered; official-domain-matching URL is tried instead."""
    tavily_results = [
        {"url": "https://www.gayot.com/restaurants/menu/dali-restaurant-tapas-bar-somerville",
         "title": "Dali on Gayot", "content": "Great tapas", "score": 0.95},
        {"url": "https://dalirestaurant.com", "title": "Dali Restaurant", "content": "menu", "score": 0.80},
    ]
    fetch_calls: list[str] = []

    async def mock_fetch(url: str):
        fetch_calls.append(url)
        return ("Patatas bravas $9\nAlbondigas $12\nGazpacho $8", url, "trafilatura")

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=None), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=tavily_results), \
         patch("agent.retrieval.fetch_and_clean", side_effect=mock_fetch):
        content, source, confidence = await retrieve_menu_content(
            "Dalis, Somerville, MA, USA", InputType.NAME
        )

    assert "gayot.com" not in source
    assert "dalirestaurant.com" in source
    assert fetch_calls[0] == "https://dalirestaurant.com"


@pytest.mark.asyncio
async def test_retrieve_name_no_places_prefers_domain_name_match():
    """Without Places API, Tavily results whose domain contains the venue name are tried first."""
    tavily_results = [
        {"url": "https://bostonchefs.com/sarma", "title": "Boston Chefs", "content": "snippet", "score": 0.95},
        {"url": "https://sarmarestaurant.com", "title": "Sarma", "content": "menu", "score": 0.80},
    ]
    fetch_calls: list[str] = []

    async def mock_fetch(url: str):
        fetch_calls.append(url)
        return ("Lamb Shank $28", url, "trafilatura")

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=None), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=tavily_results), \
         patch("agent.retrieval.fetch_and_clean", side_effect=mock_fetch):
        await retrieve_menu_content("Sarma, Somerville, MA, USA", InputType.NAME)

    # sarmarestaurant.com should be tried before bostonchefs.com despite lower Tavily score
    assert fetch_calls[0] == "https://sarmarestaurant.com"


@pytest.mark.asyncio
async def test_retrieve_name_falls_back_to_tavily_url():
    """Places returns nothing; Tavily URL fetch succeeds."""
    tavily_results = [
        {"url": "https://dishoom.com/menus", "title": "Dishoom Menu", "content": "snippet", "score": 0.9},
    ]

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=None), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=tavily_results), \
         patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock,
               return_value=("Starters\nChicken tikka £12\nDal makhani £10\nSaag paneer £10\nMains\nRoasted lamb £18",
                             "https://dishoom.com/menus", "trafilatura")) as mock_fetch:
        content, source, confidence = await retrieve_menu_content("Dishoom London", InputType.NAME)

    assert "tikka" in content
    assert source == "https://dishoom.com/menus"
    assert abs(confidence - 0.70 * 0.85) < 0.001  # trafilatura * search penalty


@pytest.mark.asyncio
async def test_retrieve_name_falls_back_to_snippets():
    """URL fetch fails; snippet content with price signals returned at low confidence.
    Yelp result is filtered out (third-party); only the official domain snippet is used.
    """
    tavily_results = [
        {"url": "https://dishoom.com/menus", "title": "Dishoom Menu",
         "content": "Starters\nChicken tikka £12\nDal makhani £10\nSaag paneer £10\nMains\nRoasted lamb £18",
         "score": 0.9},
        {"url": "https://yelp.com/dishoom", "title": "Yelp page",
         "content": "Starters\nPopular dishes £5\nGrilled chicken £8\nMains\nRoasted lamb £18",
         "score": 0.7},
    ]

    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=None), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=tavily_results), \
         patch("agent.retrieval.fetch_and_clean", new_callable=AsyncMock, side_effect=Exception("Network error")):
        content, source, confidence = await retrieve_menu_content("Dishoom London", InputType.NAME)

    assert "Dishoom Menu" in content
    assert "tikka" in content
    # Yelp snippet must not appear even though it has prices
    assert "yelp.com" not in source
    assert confidence == 0.40


@pytest.mark.asyncio
async def test_retrieve_name_all_strategies_fail():
    """Everything fails → empty content, confidence 0.0."""
    with patch("agent.retrieval.lookup_venue", new_callable=AsyncMock, return_value=None), \
         patch("agent.retrieval.search_venue_menu", new_callable=AsyncMock, return_value=[]) as mock_search:
        content, source, confidence = await retrieve_menu_content("Nonexistent Venue XYZ", InputType.NAME)

    assert content == ""
    assert confidence == 0.0


# --- image retrieval ---

@pytest.mark.asyncio
async def test_retrieve_image_calls_vision_ocr(tmp_path):
    img_file = tmp_path / "menu.jpg"
    img_file.write_bytes(b"fake-image-data")

    llm = MagicMock()
    with patch(
        "agent.retrieval.extract_text_from_image", new_callable=AsyncMock
    ) as mock_ocr:
        mock_ocr.return_value = ("Pizza Margherita [$14]", 0.85)
        content, source, confidence = await retrieve_menu_content(
            str(img_file), InputType.IMAGE, llm
        )

    assert content == "Pizza Margherita [$14]"
    assert confidence == 0.85
    assert source == str(img_file)
    mock_ocr.assert_called_once_with(b"fake-image-data", str(img_file), llm)


@pytest.mark.asyncio
async def test_retrieve_image_without_llm_raises():
    with pytest.raises(ValueError, match="LLM provider is required"):
        await retrieve_menu_content("menu.jpg", InputType.IMAGE, llm=None)


# --- PDF retrieval ---

@pytest.mark.asyncio
async def test_retrieve_pdf_calls_pdf_extract(tmp_path):
    pdf_file = tmp_path / "menu.pdf"
    pdf_file.write_bytes(b"fake-pdf-data")

    with patch("agent.retrieval.extract_text_from_pdf") as mock_pdf:
        mock_pdf.return_value = ("Pasta Carbonara [$18]", 0.85)
        content, source, confidence = await retrieve_menu_content(
            str(pdf_file), InputType.PDF
        )

    assert content == "Pasta Carbonara [$18]"
    assert confidence == 0.85
    assert source == str(pdf_file)
    mock_pdf.assert_called_once_with(b"fake-pdf-data")


@pytest.mark.asyncio
async def test_retrieve_pdf_url_downloads_and_extracts():
    mock_response = MagicMock()
    mock_response.content = b"fake-pdf-bytes"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("agent.retrieval.extract_text_from_pdf") as mock_pdf, \
         patch("agent.retrieval.httpx.AsyncClient", return_value=mock_client):
        mock_pdf.return_value = ("Pasta Carbonara [$18]", 0.85)
        content, source, confidence = await retrieve_menu_content(
            "https://example.com/menu.pdf", InputType.PDF
        )

    assert content == "Pasta Carbonara [$18]"
    assert confidence == 0.85
    assert source == "https://example.com/menu.pdf"
    mock_pdf.assert_called_once_with(b"fake-pdf-bytes")


@pytest.mark.asyncio
async def test_retrieve_pdf_empty_gives_zero_confidence(tmp_path):
    pdf_file = tmp_path / "menu.pdf"
    pdf_file.write_bytes(b"fake-pdf-data")

    with patch("agent.retrieval.extract_text_from_pdf") as mock_pdf:
        mock_pdf.return_value = ("", 0.0)
        content, source, confidence = await retrieve_menu_content(
            str(pdf_file), InputType.PDF
        )

    assert content == ""
    assert confidence == 0.0
