from pydantic import BaseModel


class FoodProfile(BaseModel):
    diet_type: str = "none"
    must_have: list[str] = []
    nice_to_have: list[str] = []
    loved_ingredients: list[str] = []
    avoid_ingredients: list[str] = []
    avoid_vibes: list[str] = []
    allergens: list[str] = []
    intolerances: list[str] = []


class TasteProfile(BaseModel):
    profile_name: str
    food: FoodProfile
