"""Tavily search tool — finds venue menu URLs and snippets."""

import os
from typing import TypedDict

from dotenv import load_dotenv

load_dotenv()

try:
    from tavily import AsyncTavilyClient  # type: ignore[import]
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False


class SearchResult(TypedDict):
    url: str
    title: str
    content: str
    score: float


# Aggregator/directory/delivery sites that never host the official menu.
# Also passed to Tavily as exclude_domains so they don't appear in results at all.
_BLOCKED_DOMAINS: set[str] = {
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
    "google.com", "facebook.com", "instagram.com",
}


def _is_blocked(url: str) -> bool:
    from urllib.parse import urlparse
    bare = urlparse(url).netloc.lower().removeprefix("www.")
    return any(bare == d or bare.endswith(f".{d}") for d in _BLOCKED_DOMAINS)


async def search_venue_menu(venue_query: str, max_results: int = 5) -> list[SearchResult]:
    """Search for a venue's menu using Tavily.

    Returns results sorted by relevance score (highest first).
    Returns an empty list if TAVILY_API_KEY is not set or the search fails.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or not _TAVILY_AVAILABLE:
        return []

    client = AsyncTavilyClient(api_key=api_key)
    query = f"{venue_query} menu"

    try:
        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
            exclude_domains=list(_BLOCKED_DOMAINS),
        )
    except Exception:
        return []

    results: list[SearchResult] = []
    for item in response.get("results", []):
        if _is_blocked(item.get("url", "")):
            continue
        results.append(
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                content=item.get("content", ""),
                score=float(item.get("score", 0.0)),
            )
        )
    return results
