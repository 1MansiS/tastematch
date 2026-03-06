from agent.venue_detector import VenueType, detect_venue_type


def test_detects_restaurant_by_content():
    result = detect_venue_type(content="Welcome to our restaurant. Grill menu available.")
    assert result == VenueType.RESTAURANT


def test_detects_coffee_shop_by_content():
    result = detect_venue_type(
        content="Specialty coffee roaster. Espresso and pour over available."
    )
    assert result == VenueType.COFFEE_SHOP


def test_detects_coffee_by_name():
    result = detect_venue_type(name="Blue Bottle Coffee")
    assert result == VenueType.COFFEE_SHOP


def test_defaults_to_restaurant_on_empty_input():
    result = detect_venue_type()
    assert result == VenueType.RESTAURANT


def test_defaults_to_restaurant_on_unknown_content():
    result = detect_venue_type(content="Welcome to our amazing place in the city.")
    assert result == VenueType.RESTAURANT


def test_coffee_wins_over_restaurant_when_more_hits():
    result = detect_venue_type(
        content="coffee espresso cafe barista — our restaurant has great coffee"
    )
    assert result == VenueType.COFFEE_SHOP
