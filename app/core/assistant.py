from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import SimpleJsonOutputParser

from .schemas import MealPlanRequest, MealPlanResponse, DishInfoResponse
from .agent import build_meal_plan, dish_info

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

INTENT_PLAN_EXISTING = "plan_existing_only"
INTENT_PLAN_WITH_NEW = "plan_with_new"
INTENT_FIND_DISH = "find_dish"
INTENT_INGR = "ingredients_for_dish"
INTENT_UNKNOWN = "unknown"

def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=MODEL, temperature=0.2)

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a routing assistant for a Ukrainian meal-planning bot.
Classify the user's request into one of intents and extract structured fields.
Return STRICT JSON only:

{
  "intent": "plan_existing_only" | "plan_with_new" | "find_dish" | "ingredients_for_dish" | "unknown",
  "days": 3,
  "dishes_uk": ["борщ", "вареники"],
  "new_similar_ratio": 0.3,
  "dish_uk": "борщ",
  "preferences": "короткий опис вподобань користувача українською"
}

Rules:
- If user clearly asks for a meal plan based ONLY on provided dishes -> intent "plan_existing_only".
- If user wants a plan with NEW similar dishes allowed -> intent "plan_with_new".
- If user wants help to find a single dish by preferences -> intent "find_dish".
- If user asks about ingredients for a specific dish -> intent "ingredients_for_dish".
- Otherwise -> "unknown".

- days: how many days of plan (if user mentions).
- dishes_uk: list of dish names in Ukrainian, if provided.
- new_similar_ratio: 0.0–1.0 how many new similar dishes to add (only for plan_with_new).
- dish_uk: single Ukrainian dish name if question is about it (find_dish / ingredients_for_dish).
- preferences: free-form Ukrainian text with user preferences.

Return ONLY JSON, no explanations.
"""
    ),
    ("human", "User message (in Ukrainian): {user_message}\nPrevious state JSON: {state_json}")
])

json_parser = SimpleJsonOutputParser()

async def _classify_intent(user_message: str, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state_json = state or {}
    chain = INTENT_PROMPT | _llm() | json_parser
    data = await chain.ainvoke({
        "user_message": user_message,
        "state_json": state_json
    })
    if not isinstance(data, dict):
        return {"intent": INTENT_UNKNOWN}
    return data

def _safe_get_json(resp: httpx.Response) -> Optional[Dict[str, Any]]:
    try:
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None

def _merge_state(parsed: Dict[str, Any], state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge LLM-parsed fields with prior session state (from previous ask)."""
    intent = parsed.get("intent", INTENT_UNKNOWN)
    days = parsed.get("days")
    dishes_uk = parsed.get("dishes_uk")
    new_ratio = parsed.get("new_similar_ratio")
    dish_uk = parsed.get("dish_uk")
    prefs = parsed.get("preferences")

    # normalize numbers
    if isinstance(days, str):
        try:
            days = int(days)
        except Exception:
            days = None
    if isinstance(new_ratio, str):
        try:
            new_ratio = float(new_ratio)
        except Exception:
            new_ratio = None

    if state and isinstance(state, dict):
        prev_intent = state.get("pending_intent")
        if prev_intent and intent == INTENT_UNKNOWN:
            intent = prev_intent
        days = days or state.get("days")
        new_ratio = new_ratio if new_ratio is not None else state.get("new_similar_ratio")
        dish_uk = dish_uk or state.get("dish_uk")
        dishes_uk = dishes_uk or state.get("dishes_uk")
        prefs = prefs or state.get("preferences")

    merged = {
        "intent": intent,
        "days": days,
        "dishes_uk": dishes_uk,
        "new_similar_ratio": new_ratio,
        "dish_uk": dish_uk,
        "preferences": prefs,
    }
    return merged

async def handle_user_message(message: str, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main entrypoint for your backend.

    Returns dict like:
    - {"type": "ask", "question": "...", "state": {...}}
    - {"type": "action", "intent": "...", "result": {...}, "state": {...}}
    """
    parsed = await _classify_intent(message, state)
    merged = _merge_state(parsed, state)

    intent = merged.get("intent", INTENT_UNKNOWN)
    days = merged.get("days")
    dishes_uk = merged.get("dishes_uk") or []
    new_ratio = merged.get("new_similar_ratio")
    dish_uk = merged.get("dish_uk")
    prefs = merged.get("preferences")

    # 1) Plan existing only
    if intent == INTENT_PLAN_EXISTING:
        if not days:
            return {
                "type": "ask",
                "question": "На скільки днів скласти план?",
                "state": {**(state or {}), "pending_intent": INTENT_PLAN_EXISTING, "dishes_uk": dishes_uk}
            }
        if not dishes_uk:
            return {
                "type": "ask",
                "question": "Перерахуйте, будь ласка, ваші страви українською.",
                "state": {**(state or {}), "pending_intent": INTENT_PLAN_EXISTING, "days": days}
            }

        req = MealPlanRequest(
            days=days,
            dishes_uk=dishes_uk,
            allow_new_similar=False,
            new_similar_ratio=0.0
        )
        plan: MealPlanResponse = await build_meal_plan(req)
        return {"type": "action", "intent": intent, "result": plan.model_dump(mode="json"), "state": {}}

    # 2) Plan with new similar dishes
    if intent == INTENT_PLAN_WITH_NEW:
        if not days:
            return {
                "type": "ask",
                "question": "На скільки днів скласти план?",
                "state": {**(state or {}), "pending_intent": INTENT_PLAN_WITH_NEW, "dishes_uk": dishes_uk,
                          "new_similar_ratio": new_ratio}
            }
        if not dishes_uk:
            return {
                "type": "ask",
                "question": "Перерахуйте, будь ласка, ваші страви українською.",
                "state": {**(state or {}), "pending_intent": INTENT_PLAN_WITH_NEW, "days": days,
                          "new_similar_ratio": new_ratio}
            }
        if new_ratio is None:
            return {
                "type": "ask",
                "question": "Яку частку нових схожих страв додати (0.0–1.0)?",
                "state": {**(state or {}), "pending_intent": INTENT_PLAN_WITH_NEW, "days": days,
                          "dishes_uk": dishes_uk}
            }

        req = MealPlanRequest(
            days=days,
            dishes_uk=dishes_uk,
            allow_new_similar=True,
            new_similar_ratio=float(new_ratio)
        )
        plan: MealPlanResponse = await build_meal_plan(req)
        return {"type": "action", "intent": intent, "result": plan.model_dump(mode="json"), "state": {}}

    # 3) Ingredients for a dish
    if intent == INTENT_INGR:
        if not dish_uk:
            return {
                "type": "ask",
                "question": "Про яку страву показати інгредієнти?",
                "state": {**(state or {}), "pending_intent": INTENT_INGR}
            }
        res: DishInfoResponse = await dish_info(dish_uk)
        return {"type": "action", "intent": intent, "result": res.model_dump(mode="json"), "state": {}}

    # 4) Find dish by preferences
    if intent == INTENT_FIND_DISH:
        if not prefs:
            return {
                "type": "ask",
                "question": "Опишіть, будь ласка, свої вподобання (що любите/не любите, калорійність тощо).",
                "state": {**(state or {}), "pending_intent": INTENT_FIND_DISH}
            }

        SUGGEST_PROMPT = ChatPromptTemplate.from_messages([
            ("system", """Ти — кулінарний асистент.

На основі побажань українською запропонуй ОДНУ страву й поверни СТРОГО JSON:
{
  "dish_uk": "Назва страви українською"
}"""),
            ("human", "Побажання: {prefs}")
        ])
        chain2 = SUGGEST_PROMPT | _llm() | json_parser
        suggestion = await chain2.ainvoke({"prefs": prefs})
        dish_name = suggestion.get("dish_uk")
        if not dish_name:
            return {
                "type": "ask",
                "question": "Не вдалося однозначно зрозуміти побажання. Спробуйте описати страву або спосіб приготування.",
                "state": {"pending_intent": INTENT_FIND_DISH}
            }
        res: DishInfoResponse = await dish_info(dish_name)
        return {"type": "action", "intent": intent, "result": res.model_dump(mode="json"), "state": {}}

    # Unknown / not supported
    return {
        "type": "ask",
        "question": (
            "Я можу: (1) план лише з ваших страв; (2) план з новими схожими; "
            "(3) підібрати страву за вподобаннями; (4) показати інгредієнти. Що потрібно?"
        ),
        "state": {}
    }
