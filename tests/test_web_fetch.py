"""Unit tests for tools/web_fetch.py extraction strategies."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.web_fetch import (
    _extract_beautifulsoup,
    _extract_json_ld_menu,
    _extract_next_data,
    _extract_nextjs_rsc,
    _extract_trafilatura,
    _extract_with_playwright,
    looks_like_menu,
    fetch_and_clean,
)


# ---------------------------------------------------------------------------
# JSON-LD extraction
# ---------------------------------------------------------------------------

def _make_json_ld_html(data: dict) -> str:
    blob = json.dumps(data)
    return f'<html><head><script type="application/ld+json">{blob}</script></head><body></body></html>'


def test_json_ld_menu_extracted():
    menu = {
        "@type": "Menu",
        "name": "Dinner Menu",
        "hasMenuSection": [
            {
                "name": "Starters",
                "description": "Small bites",
                "hasMenuItem": [
                    {
                        "name": "Soup",
                        "description": "Hot soup",
                        "offers": {"price": "5.00", "priceCurrency": "£"},
                    }
                ],
            }
        ],
    }
    html = _make_json_ld_html(menu)
    result = _extract_json_ld_menu(html)
    assert result is not None
    assert "Dinner Menu" in result
    assert "Starters" in result
    assert "Soup" in result
    assert "£5.00" in result
    assert "Hot soup" in result


def test_json_ld_restaurant_type_not_matched():
    data = {"@type": "Restaurant", "name": "Test Place"}
    html = _make_json_ld_html(data)
    assert _extract_json_ld_menu(html) is None


def test_json_ld_no_script_returns_none():
    assert _extract_json_ld_menu("<html><body>No script</body></html>") is None


def test_json_ld_malformed_json_returns_none():
    html = '<html><head><script type="application/ld+json">{bad json}</script></head></html>'
    assert _extract_json_ld_menu(html) is None


# ---------------------------------------------------------------------------
# Next.js RSC extraction
# ---------------------------------------------------------------------------

def _make_rsc_html(sections: list[dict]) -> str:
    """Wrap menu sections in a minimal Next.js RSC payload."""
    lines = []
    for i, section in enumerate(sections):
        props = {
            "currentLocationSlug": "$undefined",
            "title": section["title"],
            "description": section.get("description", ""),
            "items": section.get("items", []),
        }
        data = ["$", "$9", str(i), {"fallback": None, "children": ["$", "$L30", None, props]}]
        line_id = f"{30 + i}"
        chunk_content = f'{line_id}:{json.dumps(data)}'
        # JSON-encode the chunk as a JS string literal would be
        encoded = json.dumps(chunk_content)[1:-1]  # strip surrounding quotes
        lines.append(f'self.__next_f.push([1,"{encoded}"])')
    return "<html><body>" + "\n".join(f"<script>{l}</script>" for l in lines) + "</body></html>"


def test_nextjs_rsc_extracts_sections():
    sections = [
        {
            "title": "Starters",
            "description": "Small bites",
            "items": [
                {
                    "dish": {
                        "name": "Samosa",
                        "price": "7.50",
                        "description": "Crispy pastry",
                        "isVegan": True,
                        "isVegetarian": True,
                        "isSpicy": False,
                    }
                }
            ],
        }
    ]
    html = _make_rsc_html(sections)
    result = _extract_nextjs_rsc(html)
    assert result is not None
    assert "Starters" in result
    assert "Samosa" in result
    assert "£7.50" in result
    assert "(Ve)" in result
    assert "Crispy pastry" in result


def test_nextjs_rsc_spicy_flag():
    sections = [
        {
            "title": "Mains",
            "items": [
                {
                    "dish": {
                        "name": "Vindaloo",
                        "price": "14.00",
                        "description": "Very hot curry",
                        "isVegan": False,
                        "isVegetarian": False,
                        "isSpicy": True,
                    }
                }
            ],
        }
    ]
    result = _extract_nextjs_rsc(_make_rsc_html(sections))
    assert result is not None
    assert "(Spicy)" in result


def test_nextjs_rsc_no_payload_returns_none():
    assert _extract_nextjs_rsc("<html><body>No RSC</body></html>") is None


def test_nextjs_rsc_missing_items_key_skipped():
    # Chunk with title but no items — should not crash, should return None
    raw_data = ["$", "$9", "0", {"fallback": None, "children": ["$", "$L30", None, {"title": "X"}]}]
    encoded = json.dumps(json.dumps(raw_data))[1:-1]
    html = f'<html><script>self.__next_f.push([1,"30:{encoded}"])</script></html>'
    assert _extract_nextjs_rsc(html) is None


# ---------------------------------------------------------------------------
# __NEXT_DATA__ extraction
# ---------------------------------------------------------------------------

def test_next_data_finds_menu_sections():
    payload = {
        "props": {
            "pageProps": {
                "menuSections": [
                    {
                        "title": "Mains",
                        "description": "Hearty dishes",
                        "items": [
                            {"dish": {"name": "Burger", "price": "12.00", "description": "Juicy", "isVegan": False, "isVegetarian": False, "isSpicy": False}}
                        ],
                    }
                ]
            }
        }
    }
    html = f'<html><body><script id="__NEXT_DATA__">{json.dumps(payload)}</script></body></html>'
    result = _extract_next_data(html)
    assert result is not None
    assert "Mains" in result
    assert "Burger" in result


def test_next_data_no_script_returns_none():
    assert _extract_next_data("<html><body>nothing</body></html>") is None


def test_next_data_malformed_json_returns_none():
    html = '<html><body><script id="__NEXT_DATA__">{bad}</script></body></html>'
    assert _extract_next_data(html) is None


# ---------------------------------------------------------------------------
# _looks_like_menu helper
# ---------------------------------------------------------------------------

def test_looks_like_menu_prices_alone_sufficient():
    # 3 price hits = 2pts → meets threshold on its own
    assert looks_like_menu("Fish Tacos $12\nSoup $8\nBurger $15")

def test_looks_like_menu_gbp_prices():
    assert looks_like_menu("Fish £10\nChips £5\nDessert £7")

def test_looks_like_menu_decimal_prices():
    assert looks_like_menu("Burger 12.00\nSalad 8.50\nDessert 6.00")

def test_looks_like_menu_bare_integer_lines():
    # US menu style — prices on their own line
    assert looks_like_menu("Whipped Feta\n9\nZa'atar Bread\n13\nGigante Bean\n10")

def test_looks_like_menu_no_prices_section_and_culinary():
    # High-end menu without prices — passes via section headers + culinary vocab
    text = (
        "Starters\n"
        "Seared scallops with cauliflower purée and truffle oil\n"
        "Burrata with roasted heirloom tomatoes and basil\n\n"
        "Mains\n"
        "Braised short rib with red wine reduction and gnocchi\n"
        "Grilled sea bass with sautéed spinach and lemon aioli\n"
    )
    assert looks_like_menu(text)

def test_looks_like_menu_dietary_markers_boost():
    # Dietary markers + section header + a culinary term = 3pts
    text = "Mains\nRoasted beetroot salad (v) (gf)\nGrilled halloumi with harissa"
    assert looks_like_menu(text)

def test_looks_like_menu_generic_homepage_rejected():
    assert not looks_like_menu(
        "Welcome to our restaurant. We are open Tuesday to Sunday. "
        "Book a table online or call us. Follow us on Instagram."
    )

def test_looks_like_menu_cloudflare_block_rejected():
    assert not looks_like_menu(
        "This website is using a security service to protect itself from online attacks. "
        "The action you just performed triggered the security solution."
    )

def test_looks_like_menu_single_price_not_enough():
    # 1 price = 1pt, no other signals → below threshold
    assert not looks_like_menu("Fish Tacos $12")

def test_looks_like_menu_empty():
    assert not looks_like_menu("")


# ---------------------------------------------------------------------------
# Trafilatura fallback
# ---------------------------------------------------------------------------

def test_trafilatura_returns_text():
    html = "<html><body><article><p>Fish and Chips £10</p><p>Burger £8</p></article></body></html>"
    result = _extract_trafilatura(html)
    # trafilatura may or may not extract short content, just check it doesn't crash
    # and returns string or None
    assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# BeautifulSoup fallback
# ---------------------------------------------------------------------------

def test_beautifulsoup_strips_nav_footer():
    html = """
    <html><body>
      <nav>Nav links</nav>
      <main>Fish Curry £12</main>
      <footer>Privacy Policy</footer>
    </body></html>
    """
    result = _extract_beautifulsoup(html)
    assert "Fish Curry" in result
    assert "Nav links" not in result
    assert "Privacy Policy" not in result


def test_beautifulsoup_empty_html():
    result = _extract_beautifulsoup("<html></html>")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# fetch_and_clean integration (mocked HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_prefers_json_ld():
    menu_html = _make_json_ld_html({
        "@type": "Menu",
        "name": "Test Menu",
        "hasMenuSection": [],
    })
    mock_response = MagicMock()
    mock_response.text = menu_html
    mock_response.url = "https://example.com/menu"
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_fetch.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        text, url, method = await fetch_and_clean("https://example.com/menu")

    assert method == "json_ld"
    assert "Test Menu" in text


# ---------------------------------------------------------------------------
# Playwright headless browser strategy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_uses_playwright_when_trafilatura_finds_no_prices():
    """If trafilatura extracts text but with no prices, playwright is tried instead."""
    no_price_html = "<html><body><p>Welcome to our restaurant.</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = no_price_html
    mock_response.url = "https://example.com/menu"
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_fetch.httpx.AsyncClient") as mock_client_cls, \
         patch("tools.web_fetch._extract_trafilatura", return_value="Welcome to our restaurant."), \
         patch("tools.web_fetch._extract_with_playwright", new_callable=AsyncMock) as mock_pw:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client
        mock_pw.return_value = "Dinner Menu\nSoup $5\nFish $12"

        text, url, method = await fetch_and_clean("https://example.com/menu")

    assert method == "playwright"
    mock_pw.assert_awaited_once()


@pytest.mark.asyncio
async def test_playwright_not_installed_returns_none():
    """_extract_with_playwright returns None gracefully when playwright missing."""
    with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
        result = await _extract_with_playwright("https://example.com/menu")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_uses_playwright_when_static_strategies_fail():
    """playwright method is selected when all static strategies find nothing."""
    empty_html = "<html><body></body></html>"
    mock_response = MagicMock()
    mock_response.text = empty_html
    mock_response.url = "https://example.com/menu"
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_fetch.httpx.AsyncClient") as mock_client_cls, \
         patch("tools.web_fetch._extract_with_playwright", new_callable=AsyncMock) as mock_pw:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client
        mock_pw.return_value = "Starters: Soup £5\nMains: Fish Curry £12"

        text, url, method = await fetch_and_clean("https://example.com/menu")

    assert method == "playwright"
    assert "Soup" in text
    mock_pw.assert_awaited_once_with("https://example.com/menu")


@pytest.mark.asyncio
async def test_fetch_falls_back_to_beautifulsoup_when_playwright_unavailable():
    """beautifulsoup is used as final fallback if playwright returns None."""
    plain_html = "<html><body><p>Fish Curry £12</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = plain_html
    mock_response.url = "https://example.com/menu"
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_fetch.httpx.AsyncClient") as mock_client_cls, \
         patch("tools.web_fetch._extract_trafilatura", return_value=None), \
         patch("tools.web_fetch._extract_with_playwright", new_callable=AsyncMock) as mock_pw:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client
        mock_pw.return_value = None  # Playwright not available / failed

        text, url, method = await fetch_and_clean("https://example.com/menu")

    assert method == "beautifulsoup"
    assert "Fish Curry" in text


@pytest.mark.asyncio
async def test_fetch_falls_back_to_beautifulsoup():
    """With no structured data and playwright mocked off, falls back to beautifulsoup."""
    plain_html = "<html><body><p>Fish Curry £12</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = plain_html
    mock_response.url = "https://example.com/menu"
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_fetch.httpx.AsyncClient") as mock_client_cls, \
         patch("tools.web_fetch._extract_with_playwright", new_callable=AsyncMock, return_value=None):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        text, url, method = await fetch_and_clean("https://example.com/menu")

    assert method == "beautifulsoup"
    assert "Fish Curry" in text


@pytest.mark.asyncio
async def test_playwright_dismisses_cookie_banner_before_menu_extraction():
    """Playwright should click a visible cookie consent button before extracting menu content."""
    import sys
    from unittest.mock import MagicMock, AsyncMock

    # Build mock button that reports itself as visible
    mock_btn = AsyncMock()
    mock_btn.is_visible = AsyncMock(return_value=True)
    mock_btn.click = AsyncMock()

    mock_locator = MagicMock()
    mock_locator.first = mock_btn

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.locator = MagicMock(return_value=mock_locator)
    mock_page.query_selector_all = AsyncMock(return_value=[])
    mock_page.content = AsyncMock(return_value="<html><body><p>Breakfast $10</p></body></html>")
    mock_page.wait_for_load_state = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw_instance = AsyncMock()
    mock_pw_instance.chromium = mock_chromium

    mock_async_playwright = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_pw_instance),
        __aexit__=AsyncMock(return_value=None),
    ))

    mock_pw_module = MagicMock()
    mock_pw_module.async_playwright = mock_async_playwright

    with patch.dict(sys.modules, {
        "playwright": MagicMock(),
        "playwright.async_api": mock_pw_module,
    }), patch("tools.web_fetch._extract_trafilatura", return_value=None):
        result = await _extract_with_playwright("https://tattebakery.com/menu")

    # Cookie button visibility was checked and it was clicked
    mock_btn.is_visible.assert_awaited()
    mock_btn.click.assert_awaited()
    assert result is not None


@pytest.mark.asyncio
async def test_fetch_truncates_long_content():
    # Content well over _MAX_CHARS (32000) should be truncated; head+tail strategy
    # means we keep roughly 2/3 from head + 1/3 from tail with a separator.
    # Use "item " so trafilatura skips it but beautifulsoup returns 45 000 chars.
    long_html = "<html><body>" + ("item " * 9000) + "</body></html>"
    mock_response = MagicMock()
    mock_response.text = long_html
    mock_response.url = "https://example.com"
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_fetch.httpx.AsyncClient") as mock_client_cls, \
         patch("tools.web_fetch._extract_trafilatura", return_value=None), \
         patch("tools.web_fetch._extract_with_playwright", new_callable=AsyncMock, return_value=None):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        text, _, _ = await fetch_and_clean("https://example.com")

    # Total is _MAX_CHARS + small separator overhead
    assert len(text) <= 32100
    assert "middle content omitted" in text
