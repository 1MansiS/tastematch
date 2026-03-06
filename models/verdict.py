from pydantic import BaseModel


class VerdictModel(BaseModel):
    venue_name: str
    venue_type: str
    match_score: int  # 0–100
    match_label: str  # "Strong match", "Good match", etc.
    total_items: int
    matching_items: int
    best_picks: list[str]
    warnings: list[str]
    confidence: str  # "High", "Medium", "Low"
    source: str
