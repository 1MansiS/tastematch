from models.menu import ParsedMenu
from models.verdict import VerdictModel


def build_verdict(
    match_result: dict,
    menu: ParsedMenu,
    venue_name: str,
    venue_type: str,
    confidence: float,
) -> VerdictModel:
    if confidence >= 0.8:
        confidence_label = "High"
    elif confidence >= 0.5:
        confidence_label = "Medium"
    else:
        confidence_label = "Low"

    return VerdictModel(
        venue_name=venue_name,
        venue_type=venue_type,
        match_score=match_result.get("match_score", 0),
        match_label=match_result.get("match_label", "Unknown"),
        total_items=len(menu.items),
        matching_items=match_result.get("matching_items", 0),
        best_picks=match_result.get("best_picks", []),
        warnings=match_result.get("warnings", []),
        confidence=confidence_label,
        source=menu.source_url,
    )
