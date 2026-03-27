import json
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
_MAX_CHARS = 32000


# ---------------------------------------------------------------------------
# Extraction strategy 1: schema.org JSON-LD with @type=Menu
# ---------------------------------------------------------------------------

def _extract_json_ld_menu(html: str) -> str | None:
    """Return structured text if a schema.org Menu JSON-LD block is present."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        # Handle both single object and array of objects
        candidates = data if isinstance(data, list) else [data]
        for obj in candidates:
            if obj.get("@type") == "Menu":
                return _format_json_ld_menu(obj)
    return None


def _format_json_ld_menu(menu: dict) -> str:
    lines: list[str] = [f"=== {menu.get('name', 'Menu')} ==="]
    for section in menu.get("hasMenuSection", []):
        lines.append(f"\n--- {section.get('name', '')} ---")
        if section.get("description"):
            lines.append(section["description"])
        for item in section.get("hasMenuItem", []):
            name = item.get("name", "")
            desc = item.get("description", "")
            offer = item.get("offers", {})
            price = ""
            if isinstance(offer, dict) and offer.get("price"):
                currency = offer.get("priceCurrency", "")
                price = f"{currency}{offer['price']}"
            line = name
            if price:
                line += f" | {price}"
            lines.append(line)
            if desc:
                lines.append(f"  {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extraction strategy 2: Next.js App Router RSC payload (self.__next_f)
# ---------------------------------------------------------------------------

_RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.DOTALL)


def _decode_rsc_chunks(html: str) -> str:
    """Concatenate all __next_f RSC payload chunks into a single string."""
    full = []
    for raw in _RSC_CHUNK_RE.findall(html):
        try:
            # The chunk is a JSON-encoded string — let json.loads unescape it
            decoded = json.loads(f'"{raw}"')
            full.append(decoded)
        except (json.JSONDecodeError, ValueError):
            continue
    return "".join(full)


def _extract_nextjs_rsc(html: str) -> str | None:
    """Extract menu sections from a Next.js App Router RSC payload."""
    rsc = _decode_rsc_chunks(html)
    if not rsc:
        return None

    sections: list[dict] = []
    for line in rsc.splitlines():
        if '"items"' not in line or '"title"' not in line:
            continue
        m = re.match(r"^\w+:(.*)", line)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
            # RSC shape: ["$", component, key, {fallback, children: ["$", loader, null, section_props]}]
            if not (isinstance(data, list) and len(data) >= 4):
                continue
            children = data[3].get("children") if isinstance(data[3], dict) else None
            if not (isinstance(children, list) and len(children) >= 4):
                continue
            section_props = children[3]
            if isinstance(section_props, dict) and "items" in section_props and "title" in section_props:
                sections.append(section_props)
        except (json.JSONDecodeError, IndexError, KeyError, TypeError, AttributeError):
            continue

    if not sections:
        return None
    return _format_rsc_sections(sections)


def _format_rsc_sections(sections: list[dict]) -> str:
    lines: list[str] = []
    for section in sections:
        title = section.get("title", "")
        description = section.get("description", "")
        lines.append(f"\n=== {title} ===")
        if description:
            lines.append(description)
        for entry in section.get("items", []):
            dish = entry.get("dish") if isinstance(entry, dict) else None
            if not dish:
                continue
            name = dish.get("name", "")
            price = dish.get("price", "")
            desc = dish.get("description", "")
            flags: list[str] = []
            if dish.get("isVegan"):
                flags.append("Ve")
            elif dish.get("isVegetarian"):
                flags.append("V")
            if dish.get("isSpicy"):
                flags.append("Spicy")
            item_line = name
            if price:
                item_line += f" | £{price}"
            if flags:
                item_line += f" | ({', '.join(flags)})"
            lines.append(item_line)
            if desc:
                lines.append(f"  {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extraction strategy 3: Next.js Pages Router __NEXT_DATA__
# ---------------------------------------------------------------------------

def _extract_next_data(html: str) -> str | None:
    """Extract content from Next.js Pages Router __NEXT_DATA__ blob."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError:
        return None

    # Walk the props tree looking for menu/dish arrays
    sections = _walk_for_menu_sections(data)
    if sections:
        return _format_rsc_sections(sections)
    return None


def _walk_for_menu_sections(obj: object, depth: int = 0) -> list[dict]:
    """Recursively find dicts that look like menu sections {title, items}."""
    if depth > 10:
        return []
    if isinstance(obj, dict):
        if "title" in obj and "items" in obj and isinstance(obj["items"], list):
            return [obj]
        results: list[dict] = []
        for v in obj.values():
            results.extend(_walk_for_menu_sections(v, depth + 1))
        return results
    if isinstance(obj, list):
        results = []
        for item in obj:
            results.extend(_walk_for_menu_sections(item, depth + 1))
        return results
    return []


# ---------------------------------------------------------------------------
# Extraction strategy 4: trafilatura (reader-mode main content)
# ---------------------------------------------------------------------------

def _extract_trafilatura(html: str) -> str | None:
    try:
        import trafilatura  # type: ignore[import]
        return trafilatura.extract(html, include_tables=True, include_links=False)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Extraction strategy 5: Playwright headless browser (JS-rendered pages)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Menu content detection — multi-signal scorer
#
# High-end restaurants often omit prices, so price alone is a weak signal.
# We score across four independent signal types and require ≥3 points total.
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(
    r"[$£€]\s*\d+"        # currency symbol: $12, £9, €15
    r"|\d+\s*\.\s*\d{2}"  # decimal price: 12.00, 9.50
    r"|^\s*\d{1,3}\s*$",  # bare integer on its own line: "9", "13" (US menu style)
    re.MULTILINE,
)

# Common menu section headers
_SECTION_HEADERS: frozenset[str] = frozenset({
    "starters", "appetizers", "small plates", "shareables",
    "mains", "main course", "entrées", "entrees", "large plates",
    "sides", "side dishes",
    "desserts", "sweets", "puddings",
    "drinks", "cocktails", "wine", "spirits", "beer", "beverages",
    "brunch", "breakfast", "lunch", "dinner",
    "tasting menu", "chef's menu", "à la carte", "a la carte",
    "salads", "soups", "pasta", "pizza", "seafood",
    "specials", "today's specials", "seasonal",
})

_SECTION_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in _SECTION_HEADERS) + r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Culinary vocabulary — cooking methods, preparations, and upscale ingredients
_CULINARY_TERMS: frozenset[str] = frozenset({
    # cooking methods
    "braised", "seared", "roasted", "grilled", "smoked", "cured",
    "pickled", "poached", "fried", "baked", "marinated", "caramelized",
    "charred", "confit", "sautéed", "sauteed", "steamed", "tempura",
    # preparations & sauces
    "reduction", "aioli", "emulsion", "coulis", "jus", "purée", "puree",
    "mousse", "tartare", "carpaccio", "bruschetta", "crostini", "vinaigrette",
    "glaze", "marinade", "rub",
    # ingredients common in menus
    "truffle", "burrata", "prosciutto", "arugula", "ricotta", "mozzarella",
    "parmesan", "pancetta", "chorizo", "halloumi", "tahini", "hummus",
    "za'atar", "sumac", "harissa", "miso", "ponzu", "yuzu", "dashi",
    "gnocchi", "risotto", "focaccia", "sourdough", "brioche",
    "ribeye", "tenderloin", "short rib", "duck breast", "sea bass",
    "scallops", "octopus", "burgers", "flatbread",
})

_CULINARY_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _CULINARY_TERMS) + r")\b",
    re.IGNORECASE,
)

# Dietary markers — very common even on price-free fine dining menus
_DIETARY_RE = re.compile(
    r"\(v\)|\(vg\)|\(ve\)|\(gf\)|\(df\)|\(pb\)|\(n\)"
    r"|vegetarian|vegan|gluten.free|dairy.free|plant.based|nut.free|contains nuts",
    re.IGNORECASE,
)

# Score threshold to be considered menu content.
# Threshold of 2 means:
#   - 3+ prices alone are sufficient (regular menus with price tags)
#   - 2+ section headers alone are sufficient
#   - 5+ culinary terms alone are sufficient
#   - 1 price + any other signal is sufficient
#   - Single-signal hits (1 price, 1 header, 2 culinary words) are not enough alone
_MENU_SCORE_THRESHOLD = 2


def looks_like_menu(text: str) -> bool:
    """Multi-signal check: returns True if *text* looks like restaurant menu content.

    Scores across four independent signals (max 7 pts), requires ≥3:
      - Price signals   0–2 pts  (≥1 hit = 1pt, ≥3 hits = 2pts)
      - Section headers 0–2 pts  (≥1 header = 1pt, ≥2 headers = 2pts)
      - Culinary vocab  0–2 pts  (≥2 terms = 1pt, ≥5 terms = 2pts)
      - Dietary markers 0–1 pt   (≥1 marker = 1pt)
    """
    if not text:
        return False

    score = 0

    price_hits = len(_PRICE_RE.findall(text))
    if price_hits >= 3:
        score += 2
    elif price_hits >= 1:
        score += 1

    section_hits = len(_SECTION_RE.findall(text))
    if section_hits >= 2:
        score += 2
    elif section_hits >= 1:
        score += 1

    culinary_hits = len(_CULINARY_RE.findall(text))
    if culinary_hits >= 5:
        score += 2
    elif culinary_hits >= 2:
        score += 1

    if _DIETARY_RE.search(text):
        score += 1

    return score >= _MENU_SCORE_THRESHOLD


_MENU_LINK_KEYWORDS: frozenset[str] = frozenset({
    "menu", "menus", "food", "dine", "dining", "dinner", "lunch",
    "brunch", "breakfast", "eat", "drinks", "cocktails", "wine",
})


def find_menu_links(html: str, base_url: str) -> list[str]:
    """Find same-domain menu-related links in *html*, ranked by keyword score.

    Scans anchor tags for hrefs that share the same domain as *base_url* and
    whose href path or link text contains a menu-related keyword.  Hash
    fragments are preserved (e.g. /#dinner-menu) so that Playwright can
    navigate to the correct section.  Returns deduplicated absolute URLs
    sorted by relevance score, highest first.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_netloc = urlparse(base_url).netloc

    seen: set[str] = set()
    candidates: list[tuple[int, str]] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.netloc != base_netloc:
            continue
        # Normalize: strip query params but keep fragment (e.g. /#dinner-menu)
        normalized = parsed._replace(query="").geturl()
        if normalized in seen or normalized == base_url:
            continue
        seen.add(normalized)

        href_lower = href.lower()
        text_lower = (a.get_text(strip=True) or "").lower()
        score = sum(1 for kw in _MENU_LINK_KEYWORDS if kw in href_lower or kw in text_lower)
        if score > 0:
            candidates.append((score, abs_url))

    candidates.sort(key=lambda x: -x[0])
    return [url for _, url in candidates]


async def fetch_raw_html(url: str) -> str:
    """Fetch *url* and return raw HTML without any extraction."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=_HEADERS)
        response.raise_for_status()
        return response.text


async def _extract_with_playwright(url: str) -> str | None:
    """Render *url* with a headless Chromium browser and extract content.

    Used for JS-heavy restaurant sites where the menu is populated after
    JavaScript runs (dropdown menus, SPA frameworks, AJAX-loaded content).
    Returns None if Playwright is not installed or the render fails.
    After rendering, clicks any visible menu-tab / dropdown elements to expand
    hidden sections, then re-tries structured strategies on the full HTML.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore[import]
    except ImportError:
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30_000)

            # Dismiss cookie consent / GDPR banners before interacting with the page
            _COOKIE_SELECTORS = [
                "button:has-text('Accept All')",
                "button:has-text('Accept all')",
                "button:has-text('Accept')",
                "button:has-text('I Accept')",
                "button:has-text('Allow All')",
                "button:has-text('Allow all')",
                "button:has-text('Save My Preferences')",
                "button:has-text('Got it')",
                "button:has-text('OK')",
                "[aria-label*='cookie' i] button",
                "#onetrust-accept-btn-handler",
                ".cookie-consent-accept",
                ".cc-accept",
            ]
            for sel in _COOKIE_SELECTORS:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1_000):
                        await btn.click(timeout=2_000)
                        await page.wait_for_load_state("networkidle", timeout=5_000)
                        break
                except Exception:
                    continue

            # Click menu-section tabs / dropdowns to reveal hidden content
            _MENU_SELECTORS = [
                "nav a", "ul.menu-nav a", ".menu-tabs a", ".menu-tab",
                "[role='tab']", ".accordion-header", ".menu-category",
                "select[name*='menu']", ".dropdown-toggle",
                "a[href*='#filter']", "a[href*='#menu']", "a[href*='#tab']",
                "[data-filter]", "[data-tab]",
            ]
            for selector in _MENU_SELECTORS:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements[:8]:  # cap clicks to avoid infinite loops
                        await el.click(timeout=2_000)
                        await page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception:
                    continue

            html = await page.content()
            await browser.close()
    except Exception:
        return None

    # Re-try structured strategies on the fully-rendered HTML
    result = _extract_json_ld_menu(html)
    if result:
        return result
    result = _extract_trafilatura(html)
    if result:
        return result
    return _extract_beautifulsoup(html)


# ---------------------------------------------------------------------------
# Extraction strategy 6: BeautifulSoup plain-text fallback
# ---------------------------------------------------------------------------

def _extract_beautifulsoup(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

#: Maps extraction method name → confidence boost (used by retrieval layer)
EXTRACTION_METHOD: str = "unknown"


async def fetch_and_clean(url: str) -> tuple[str, str, str]:
    """Fetch *url* and return ``(clean_text, final_url, method)``.

    *method* is one of: ``json_ld``, ``nextjs_rsc``, ``next_data``,
    ``trafilatura``, ``playwright``, ``beautifulsoup``.  The retrieval layer
    uses it to set confidence.
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=_HEADERS)
        response.raise_for_status()
        final_url = str(response.url)
        html = response.text

    # Try extraction strategies in priority order
    result = _extract_json_ld_menu(html)
    if result:
        method = "json_ld"
    else:
        result = _extract_nextjs_rsc(html)
        if result:
            method = "nextjs_rsc"
        else:
            result = _extract_next_data(html)
            if result:
                method = "next_data"
            else:
                trafilatura_result = _extract_trafilatura(html)
                if trafilatura_result and looks_like_menu(trafilatura_result):
                    result = trafilatura_result
                    method = "trafilatura"
                else:
                    # Static strategies exhausted (or trafilatura found no prices)
                    # — try headless browser for JS-rendered / dropdown menus
                    result = await _extract_with_playwright(url)
                    if result:
                        method = "playwright"
                    else:
                        # Fall back to trafilatura text even without prices, then BS4
                        result = trafilatura_result or _extract_beautifulsoup(html)
                        method = "beautifulsoup"

    if len(result) > _MAX_CHARS:
        # Keep head + tail so menus where drinks are at the top and food at the
        # bottom both survive truncation.  The middle (navigation, promo text,
        # duplicate descriptions) is the least-valuable content to lose.
        head = result[: _MAX_CHARS * 2 // 3]
        tail = result[-(_MAX_CHARS // 3) :]
        result = head + "\n...[middle content omitted for length]...\n" + tail

    return result, final_url, method
