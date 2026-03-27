"""Google Places lookup — resolves venue name/address to website URL.

Requires GOOGLE_PLACES_API_KEY in .env and the googlemaps package.
Returns None gracefully when neither is available.
"""

import asyncio
import os
from typing import TypedDict

from dotenv import load_dotenv

load_dotenv()


class PlacesResult(TypedDict):
    name: str
    website: str
    address: str
    place_id: str


async def lookup_venue(query: str) -> PlacesResult | None:
    """Look up a venue by name/address using Google Places API.

    Returns a PlacesResult with the venue's official website URL,
    or None if no key is configured, the package is missing, or the
    lookup fails.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return None

    try:
        import googlemaps  # type: ignore[import]
    except ImportError:
        return None

    def _sync_lookup() -> PlacesResult | None:
        gmaps = googlemaps.Client(key=api_key)
        try:
            result = gmaps.find_place(
                input=query,
                input_type="textquery",
                fields=["name", "place_id", "formatted_address"],
            )
            candidates = result.get("candidates", [])
            if not candidates:
                return None

            place_id = candidates[0]["place_id"]
            details = gmaps.place(
                place_id=place_id,
                fields=["name", "website", "formatted_address"],
            )
            p = details.get("result", {})
            return PlacesResult(
                name=p.get("name", ""),
                website=p.get("website", ""),
                address=p.get("formatted_address", ""),
                place_id=place_id,
            )
        except Exception:
            return None

    return await asyncio.to_thread(_sync_lookup)
