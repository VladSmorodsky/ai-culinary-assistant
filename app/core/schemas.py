from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, conlist, field_validator

MEAL_TITLES_UK = ["сніданок", "обід", "вечеря"]

class NutritionItem(BaseModel):
    nutrition_title: str
    value: float
    unit: str

class DishItem(BaseModel):
    dish_title: str
    short_description: str
    nutrition: List[NutritionItem]

class MealItem(BaseModel):
    meal_title: str
    dishes: conlist(DishItem, min_length=1)

    @field_validator("meal_title")
    @classmethod
    def normalize_title(cls, v: str) -> str:
        v = v.strip().lower()
        map_alias = {"сніданок":"сніданок","обід":"обід","ланч":"обід","вечеря":"вечеря"}
        return map_alias.get(v, v)

class DayPlan(BaseModel):
    day_number: int = Field(..., ge=1)
    meals: conlist(MealItem, min_length=1)

class MealPlanResponse(BaseModel):
    days: conlist(DayPlan, min_length=1)

class IngredientsPair(BaseModel):
    uk: List[str]
    en: List[str]

class DishInfoRequest(BaseModel):
    dish_uk: str

class DishInfoResponse(BaseModel):
    dish_title: str
    short_description: str
    recipe: str
    ingredients: IngredientsPair
    nutrition: List[NutritionItem]

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