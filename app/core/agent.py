from __future__ import annotations
import json, os, re
from typing import Any, Dict, List, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
import httpx

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import SimpleJsonOutputParser

from .schemas import MealPlanRequest, MealPlanResponse, DishInfoResponse, IngredientsPair, NutritionItem, DayPlan
from .mcp_client import MCPClient
from .storage import FileKV

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=MODEL, temperature=0.3)

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
BARCODES_PATH = os.path.join(DATA_DIR, "barcodes.json")
NUTRITION_PATH = os.path.join(DATA_DIR, "nutrition.json")

barcode_kv = FileKV(BARCODES_PATH)     # name -> [barcodes]
nutrition_kv = FileKV(NUTRITION_PATH)  # barcode -> {product, nutrition}

json_parser = SimpleJsonOutputParser()

PLAN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ти — асистент-нутриціолог. Твоя задача — скласти план харчування українською мовою.

Вхідні дані:
- Кількість днів: {days}
- Список страв українською мовою (може бути порожнім): {dishes_uk}
- Чи дозволено додавати нові подібні страви: {allow_new_similar}
- Частка нових подібних страв (0.0–1.0): {new_similar_ratio}

Вихідні вимоги:
- Поверни СТРОГО валідний JSON.
- Поля й ключі — АНГЛІЙСЬКОЮ.
- Опис страв (title, description, recipe) — УКРАЇНСЬКОЮ.
- НЕ додавай нутрієнти (protein, carbs тощо) в цьому кроці.

Формат виходу:
{{
  "days": [
    {{
      "day": 1,
      "meals": [
        {{
          "meal_type": "breakfast" | "lunch" | "dinner" | "snack",
          "dishes": [
            {{
              "dish_title": "...",
              "short_description": "1–2 короткі речення"
            }}
          ]
        }}
      ]
    }}
  ]
}}

- Страви повинні бути реалістні, збалансовані й зрозумілі в Україні.
- Якщо дозволено додавати нові подібні, вони мають бути стилістично й інгредієнтно схожі на наявні.
- НЕ додавай нутрієнти в цьому кроці.
"""),
    ("human", "Згенеруй план харчування.")
])

NUTRITION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ти — експерт з харчування.

Отримуєш список страв з назвами українською та базовою інформацією.
Твоя задача — для кожної страви визначити перелік основних нутрієнтів:

Формат нутрієнтів:
{{
  "nutrition": [
    {{
      "nutrition_title": "Калорії",
      "value": 350,
      "unit": "kcal"
    }},
    {{
      "nutrition_title": "Білки",
      "value": 20,
      "unit": "g"
    }}
  ]
}}

Вимоги:
- Поверни СТРОГО валідний JSON.
- Ключі й поля — АНГЛІЙСЬКОЮ.
- Значення nutrition_title — УКРАЇНСЬКОЮ.
- Не придумуй надто деталізовані нутрієнти (достатньо 5–10 ключових на страву).
- Якщо інформацію важко оцінити, зроби найкращу обґрунтовану оцінку.

Формат загального відповіді:
{{
  "items": [
    {{
      "dish_uk": "Борщ",
      "nutrition": [ ... ]
    }}
  ]
}}
"""),
    ("human", "Ось JSON плану харчування українською: {plan_json}")
])

DISH_INFO_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ти — кулінарний асистент.

Для вказаної страви українською мовою поверни СТРОГО валідний JSON такого формату:
{{
  "dish_title": "Назва страви українською",
  "short_description": "1–2 короткі речення українською",
  "recipe": "Детальний рецепт українською",
  "ingredients": {{
    "uk": ["інгредієнт 1", "інгредієнт 2"],
    "en": ["ingredient 1", "ingredient 2"]
  }},
  "nutrition": [
    {{
      "nutrition_title": "Калорії",
      "value": 350,
      "unit": "kcal"
    }}
  ]
}}

Вимоги:
- Опис і рецепт — українською.
- ingredients.uk — українською; ingredients.en — англійською.
- nutritional_title — українською.
- Якщо чогось не знаєш, зроби найкращу обґрунтовану оцінку.
"""),
    ("human", "Страва: {dish_uk}")
])

TRANSLATE_NUTRITION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ти — перекладач. Отримуєш JSON списку нутрієнтів українською і маєш перекласти лише їхні назви на англійську.

Вхід:
{{
  "nutrition": [
    {{
      "nutrition_title": "Калорії",
      "value": 350,
      "unit": "kcal"
    }}
  ]
}}

Поверни:
СТРОГО валідний JSON у форматі:
{{
  "nutrition": [
    {{
      "name": "Calories",
      "value": 350,
      "unit": "kcal"
    }}
  ]
}}

- Тільки переклад назви; value та unit залишай без змін.
- Не додавай зайвих полів.
"""),
    ("human", "Ось JSON списку нутрієнтів українською: {nutrition_json}")
])

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(0.5, 1.5))
async def _generate_meal_plan(req: MealPlanRequest) -> MealPlanResponse:
    chain = PLAN_PROMPT | _llm() | json_parser
    data = await chain.ainvoke({
        "days": req.days,
        "dishes_uk": ", ".join(req.dishes_uk) if req.dishes_uk else "(порожньо)",
        "allow_new_similar": str(bool(req.allow_new_similar)).lower(),
        "new_similar_ratio": req.new_similar_ratio
    })
    return MealPlanResponse(**data)

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(0.5, 1.5))
async def _enrich_with_nutrition(plan: MealPlanResponse) -> MealPlanResponse:
    serialized = plan.model_dump(mode="json")
    chain = NUTRITION_PROMPT | _llm() | json_parser
    data = await chain.ainvoke({"plan_json": json.dumps(serialized, ensure_ascii=False)})
    nutrition_map: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    for item in data.get("items", []):
        day = item.get("day")
        dish_title = item.get("dish_uk")
        if day is None or dish_title is None:
            continue
        nutrition_map[(day, dish_title)] = item.get("nutrition", [])

    for day in plan.days:
        for meal in day.meals:
            for dish in meal.dishes:
                key = (day.day, dish.dish_title)
                if key in nutrition_map:
                    dish.nutrition = [
                        NutritionItem(
                            nutrition_title=n.get("nutrition_title") or n.get("title") or n.get("name", ""),
                            value=float(n.get("value", 0) or 0),
                            unit=n.get("unit", "")
                        ) for n in nutrition_map[key] if isinstance(n, dict)
                    ]
    return plan

async def build_meal_plan(req: MealPlanRequest) -> MealPlanResponse:
    plan = await _generate_meal_plan(req)
    plan = await _enrich_with_nutrition(plan)
    return plan

async def _fetch_product_by_barcode(barcode: str) -> Dict[str, Any]:
    cached = nutrition_kv.get(barcode)
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json")
            resp.raise_for_status()
        except Exception:
            return {}

    data = resp.json()
    product = data.get("product") or {}
    nutriments = product.get("nutriments") or {}
    nutrition = []
    for key, value in nutriments.items():
        match = re.match(r"(.+)_value", key)
        if not match:
            continue
        base_name = match.group(1)
        unit = nutriments.get(f"{base_name}_unit", "")
        nutrition.append({
            "nutrition_title": base_name,
            "value": value,
            "unit": unit
        })

    result = {
        "product_name": product.get("product_name", ""),
        "nutrition": nutrition
    }
    nutrition_kv.set(barcode, result)
    return result

async def dish_info(dish_uk: str) -> DishInfoResponse:
    mcp_client = MCPClient()
    external = await mcp_client.get_dish_info(dish_uk)

    dish_title = external.get("dish_title") or dish_uk
    short_description = external.get("short_description", "")
    recipe = external.get("recipe", "")
    ingredients = external.get("ingredients", {})
    nutrition_external = external.get("nutrition", [])

    en_list = ingredients.get("en") or []
    if not en_list and ingredients.get("uk"):
        ingredients_text = ", ".join(ingredients["uk"])
        trans_prompt = ChatPromptTemplate.from_messages([
            ("system", "Ти — перекладач. Переклади список інгредієнтів з української на англійську."),
            ("human", "Список інгредієнтів: {ingredients}")
        ])
        chain = trans_prompt | _llm() | json_parser
        trans = await chain.ainvoke({"ingredients": ingredients_text})
        en_list = trans.get("ingredients_en") or []

    nutrition_items = [
        NutritionItem(
            nutrition_title=n.get("nutrition_title") or n.get("title") or n.get("name", ""),
            value=float(n.get("value", 0) or 0),
            unit=n.get("unit", "")
        ) for n in nutrition_external if isinstance(n, dict)
    ]

    base = {
        "dish_title": dish_title,
        "short_description": short_description,
        "recipe": recipe,
        "ingredients": {
            "uk": ingredients.get("uk", []),
            "en": en_list
        },
        "nutrition": [n.model_dump(mode="json") for n in nutrition_items]
    }

    return DishInfoResponse(
        dish_title=base.get("dish_title", dish_uk),
        short_description=base.get("short_description", ""),
        recipe=base.get("recipe", ""),
        ingredients=IngredientsPair(uk=base.get("ingredients", {}).get("uk", []),
                                    en=en_list),
        nutrition=[
            NutritionItem(
                nutrition_title=n.get("nutrition_title") or n.get("title") or n.get("name", ""),
                value=float(n.get("value", 0) or 0),
                unit=n.get("unit", "")
            ) for n in nutrition_items if isinstance(n, NutritionItem)
        ]
    )
