from pathlib import Path
from urllib.parse import urlparse

import httpx

from agent.router import InputType
from llm.base import LLMProvider
from tools.pdf_extract import extract_text_from_pdf
from tools.places_lookup import lookup_venue
from tools.search import search_venue_menu
from tools.vision_ocr import extract_text_from_image
from tools.web_fetch import fetch_and_clean, fetch_raw_html, find_menu_links, looks_like_menu

# Confidence by extraction method — higher = more structured/reliable data
_METHOD_CONFIDENCE: dict[str, float] = {
    "json_ld": 1.0,
    "nextjs_rsc": 0.95,
    "next_data": 0.90,
    "trafilatura": 0.70,
    "playwright": 0.75,
    "beautifulsoup": 0.50,
}

# Confidence multiplier for search-found URLs (not the official direct URL)
_SEARCH_URL_PENALTY: float = 0.85

# Known third-party aggregator / review / delivery domains — never contain the
# official restaurant menu, so we skip them in Tavily results.
# Keep in sync with _BLOCKED_DOMAINS in tools/search.py.
_THIRD_PARTY_DOMAINS: frozenset[str] = frozenset({
    # Reviews & discovery
    "yelp.com", "tripadvisor.com", "zagat.com", "foursquare.com",
    "zomato.com", "opentable.com", "resy.com", "tock.com", "exploretock.com",
    # City guides & local directories
    "bostonchefs.com", "timeout.com", "eater.com", "thefork.com",
    "restaurantji.com", "menuism.com", "allmenus.com", "menupages.com",
    "citysearch.com", "infatuation.com", "tableagent.com",
    "gayot.com", "fodors.com", "lonelyplanet.com", "frommers.com",
    # Delivery & ordering
    "doordash.com", "grubhub.com", "ubereats.com", "seamless.com",
    "deliveroo.com", "just-eat.com", "postmates.com", "eat24.com",
    "chownow.com", "toasttab.com",
    # Single-platform / aggregated menu hosts
    "singleplatform.com", "places.singleplatform.com",
    # Social / maps
    "google.com", "maps.google.com", "facebook.com", "instagram.com",
})


def _is_third_party(url: str) -> bool:
    bare = urlparse(url).netloc.lower().removeprefix("www.")
    return any(bare == d or bare.endswith(f".{d}") for d in _THIRD_PARTY_DOMAINS)


def _venue_name_from_query(query: str) -> str:
    """Extract the venue name (first comma-token) from a name/address query."""
    return query.split(",")[0].strip().lower()


def _domain_matches_venue(url: str, venue_name: str) -> bool:
    """True if the URL's domain contains the venue name (or a meaningful part of it).

    Tries the full name first, then progressively strips trailing characters to
    handle possessives/plurals (e.g. "Dalis" → tries "dalis", then "dali").
    """
    if not venue_name or len(venue_name) < 3:
        return False
    bare = urlparse(url).netloc.lower().removeprefix("www.")
    bare_alnum = "".join(c for c in bare if c.isalnum())
    name_alnum = "".join(c for c in venue_name if c.isalnum())
    # Try full name, then progressively shorter prefixes (minimum 4 chars)
    for length in range(len(name_alnum), 3, -1):
        if name_alnum[:length] in bare_alnum:
            return True
    return False


async def _try_menu_links(base_url: str) -> tuple[str, str, float] | None:
    """Fetch *base_url* HTML, discover same-domain menu links, try each one.

    Used when the initial fetch of the official homepage returned only weak
    beautifulsoup content (no price signals).  Hash fragments are preserved so
    Playwright can navigate to sections like /#dinner-menu.
    Returns (content, final_url, confidence) on first success, else None.
    """
    try:
        html = await fetch_raw_html(base_url)
    except Exception:
        return None

    links = find_menu_links(html, base_url)
    for link in links[:4]:
        try:
            content, final_url, method = await fetch_and_clean(link)
            if content:
                return content, final_url, _METHOD_CONFIDENCE.get(method, 0.5)
        except Exception:
            continue
    return None


async def _retrieve_by_name(venue_query: str) -> tuple[str, str, float]:
    """Multi-strategy retrieval for venue name / address queries.

    Strategy 1a: Google Places → official website URL → web_fetch
    Strategy 1b: Menu link discovery on official site (when 1a gives weak content)
    Strategy 2:  Tavily search → filter third-party → fetch candidate URLs
    Strategy 3:  Tavily snippet content directly (low confidence)
    Strategy 4:  Nothing worked → empty result, confidence 0.0
    """
    official_domain: str | None = None

    # Strategy 1a: Google Places → official website → fetch
    place = await lookup_venue(venue_query)
    if place and place["website"]:
        official_url = place["website"]
        official_domain = urlparse(official_url).netloc
        try:
            content, final_url, method = await fetch_and_clean(official_url)
            if content and (method != "beautifulsoup" or looks_like_menu(content)):
                confidence = _METHOD_CONFIDENCE.get(method, 0.5)
                return content, final_url, confidence

            # Strategy 1b: homepage was weak — crawl it for menu links
            result = await _try_menu_links(official_url)
            if result:
                return result
        except Exception:
            pass

    # Strategy 2: Tavily search → filter aggregators, prefer official domain
    results = await search_venue_menu(venue_query)
    official_results = [r for r in results if official_domain and official_domain in r["url"]]
    other_results = [
        r for r in results
        if r not in official_results and not _is_third_party(r["url"])
    ]
    # When no official domain is known, surface domain-name matches first
    if not official_domain:
        venue_name = _venue_name_from_query(venue_query)
        other_results.sort(key=lambda r: _domain_matches_venue(r["url"], venue_name), reverse=True)
    for result in (official_results + other_results)[:4]:
        url = result["url"]
        if not url:
            continue
        try:
            content, final_url, method = await fetch_and_clean(url)
            if content and looks_like_menu(content):
                confidence = _METHOD_CONFIDENCE.get(method, 0.5) * _SEARCH_URL_PENALTY
                return content, final_url, confidence
        except Exception:
            continue

    # Strategy 3: Tavily snippet content (partial, no full menu)
    # Only use snippets from non-third-party sources that look food-related.
    snippet_results = [
        r for r in results
        if r["content"] and not _is_third_party(r["url"])
    ]
    if snippet_results:
        combined = "\n\n".join(
            f"[{r['title']}]\n{r['content']}" for r in snippet_results[:3]
        )
        if combined and looks_like_menu(combined):
            source = snippet_results[0]["url"] or venue_query
            return combined, source, 0.40

    # Strategy 4: Nothing worked
    return "", venue_query, 0.0


async def retrieve_menu_content(
    user_input: str, input_type: InputType, llm: LLMProvider | None = None
) -> tuple[str, str, float]:
    """Return (content, source, confidence).

    confidence is 0.0–1.0 reflecting how likely the content contains a full menu.
    llm is required when input_type is IMAGE.
    """
    if input_type == InputType.URL:
        content, final_url, method = await fetch_and_clean(user_input)
        confidence = _METHOD_CONFIDENCE.get(method, 0.5) if content else 0.0
        return content, final_url, confidence

    if input_type == InputType.NAME:
        return await _retrieve_by_name(user_input)

    if input_type == InputType.IMAGE:
        if llm is None:
            raise ValueError("An LLM provider is required for image input")
        image_bytes = Path(user_input).read_bytes()
        text, confidence = await extract_text_from_image(image_bytes, user_input, llm)
        return text, user_input, confidence

    if input_type == InputType.PDF:
        if user_input.startswith(("http://", "https://")):
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(user_input)
                response.raise_for_status()
                pdf_bytes = response.content
        else:
            pdf_bytes = Path(user_input).read_bytes()
        text, confidence = extract_text_from_pdf(pdf_bytes)
        return text, user_input, confidence

    raise ValueError(f"Unsupported input type: {input_type!r}")
