from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

MEAL_TITLES_UK = ["сніданок", "обід", "вечеря"]


class NutritionItem(BaseModel):
    nutrition_title: str
    value: float
    unit: str


class DishItem(BaseModel):
    dish_title: str
    short_description: str
    short_recipe: str = ""  # newly added concise recipe (1–3 sentences or steps)
    nutrition: List[NutritionItem]


class MealItem(BaseModel):
    meal_title: str
    dishes: List[DishItem] = Field(..., min_length=1)

    @field_validator("meal_title")
    @classmethod
    def normalize_title(cls, v: str) -> str:
        v = v.strip().lower()
        map_alias = {
            "сніданок": "сніданок",
            "обід": "обід",
            "ланч": "обід",
            "вечеря": "вечеря",
        }
        return map_alias.get(v, v)


class DayPlan(BaseModel):
    day_number: int = Field(..., ge=1)
    meals: List[MealItem] = Field(..., min_length=1)


class MealPlanResponse(BaseModel):
    days: List[DayPlan] = Field(..., min_length=1)


# Deprecated structure (kept for potential backward compatibility)
class IngredientsPair(BaseModel):  # pragma: no cover
    uk: List[str]
    en: List[str]
    barcodes: List[str] = Field(
        default_factory=list
    )  # aligned list of barcodes (EAN/UPC) for ingredients


class IngredientItem(BaseModel):
    uk: str
    nutrition: List[NutritionItem] = Field(
        default_factory=list
    )  # nutrition data for this ingredient


class DishInfoRequest(BaseModel):
    dish_uk: str


class DishInfoResponse(BaseModel):
    dish_title: str
    short_description: str
    short_recipe: str = ""  # new field
    recipe: str  # keeping original longer recipe for backward compatibility
    # Ingredients with nutrition data for each ingredient
    ingredients: List[IngredientItem]


class MealPlanRequest(BaseModel):
    days: int = Field(..., ge=1, le=30)
    dishes_uk: List[str] = Field(default_factory=list)
    allow_new_similar: bool = False
    new_similar_ratio: float = Field(0.0, ge=0.0, le=1.0)

    @field_validator("new_similar_ratio")
    @classmethod
    def ratio_guard(cls, v, info):
        allow = info.data.get("allow_new_similar", False)
        if not allow and v != 0.0:
            return 0.0
        return v


class AssistantRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_state: Optional[Dict[str, Any]] = None


class AssistantResponse(BaseModel):
    type: str
    intent: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    question: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
