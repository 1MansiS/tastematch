from enum import Enum

_COFFEE_KEYWORDS = {"coffee", "cafe", "café", "espresso", "brew", "roaster", "barista"}
_RESTAURANT_KEYWORDS = {
    "restaurant",
    "kitchen",
    "grill",
    "bistro",
    "eatery",
    "diner",
    "tavern",
}


class VenueType(str, Enum):
    RESTAURANT = "restaurant"
    COFFEE_SHOP = "coffee_shop"


def detect_venue_type(name: str = "", content: str = "") -> VenueType:
    """Infer venue type from name and/or page content. Defaults to restaurant."""
    text = f"{name} {content[:500]}".lower()
    coffee_hits = sum(1 for kw in _COFFEE_KEYWORDS if kw in text)
    restaurant_hits = sum(1 for kw in _RESTAURANT_KEYWORDS if kw in text)
    if coffee_hits > restaurant_hits:
        return VenueType.COFFEE_SHOP
    return VenueType.RESTAURANT
