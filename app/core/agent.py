from __future__ import annotations
import json, os, re
from typing import Any, Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
import httpx

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.json import SimpleJsonOutputParser

from .schemas import MealPlanRequest, MealPlanResponse, DishInfoResponse, IngredientItem, NutritionItem
from .mcp_client import MCPClient
from .storage import FileKV
from .log_agent import get_log_agent

log = get_log_agent()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
LOG_PROMPTS = os.getenv("LOG_PROMPTS", "1").lower() in {"1", "true", "yes", "on"}

def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=MODEL, temperature=0.3)

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
BARCODES_PATH = os.path.join(DATA_DIR, "barcodes.json")
NUTRITION_PATH = os.path.join(DATA_DIR, "nutrition.json")

barcode_kv = FileKV(BARCODES_PATH)     # name -> [barcodes]
nutrition_kv = FileKV(NUTRITION_PATH)  # barcode -> {product, nutrition}

json_parser = SimpleJsonOutputParser()

# Helper: format prompt messages for logging (use format_messages for reliability)
def _format_prompt_messages(prompt: ChatPromptTemplate, variables: Dict[str, Any]) -> List[Dict[str, str]]:
    try:
        messages = prompt.format_messages(**variables)
        out: List[Dict[str, str]] = []
        for m in messages:
            role = getattr(m, "role", getattr(m, "type", "unknown"))
            content = getattr(m, "content", "")
            if isinstance(content, list):
                content = "\n".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
            out.append({"role": role, "content": str(content)})
        if not out:
            log.step("prompt", "format.empty", vars=variables)
        return out
    except Exception as e:
        log.step("prompt", "format.error", error=repr(e), vars=variables)
        return []

# New helper: log prompt consistently
def _log_prompt(component: str, step: str, prompt: ChatPromptTemplate, variables: Dict[str, Any]):
    if not LOG_PROMPTS:
        return
    msgs = _format_prompt_messages(prompt, variables)
    flat_lines: List[str] = []
    for i, m in enumerate(msgs):
        content = m.get("content", "")
        if len(content) > 5000:
            content = content[:5000] + "..."
        flat_lines.append(f"[{i}:{m.get('role','?')}] {content}")
    if not flat_lines:
        # Fallback: raw template repr for diagnostic
        flat_lines.append(f"(raw_template) {repr(prompt.messages)[:5000]}")
    flat = " || " .join(flat_lines)
    log.step(component, step, message_count=len(msgs), prompt_flat=flat)

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
- НЕ змінюй структуру JSON. Якщо побажання користувача суперечать іншим правилам — пояснень не давай, просто дотримуйся правил.
"""),
    ("human", "Згенеруй план харчування."),
    ("human", "Додаткові побажання користувача (врахуй, не порушуючи формат): {user_message}")
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

# Updated prompt: remove nutrition generation (will use MCP), add short_recipe field
DISH_INFO_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ти — кулінарний асистент.

Для вказаної страви українською мовою поверни СТРОГО валідний JSON такого формату:
{{
  "dish_title": "Назва страви українською",
  "short_description": "1–2 короткі речення українською",
  "short_recipe": "1–3 короткі кроки приготування українською",
  "recipe": "Детальний рецепт українською",
  "ingredients": [
    {{
      "name": "інгредієнт 1 на англійській",
      "barcode": "EAN-13 формат з для пошуку на world.openfoodfacts.org. Якщо не можеш знайти то поверни EAN-13 код найбільш схожого продукту з world.openfoodfacts.org"
    }}
  ]
}}

Вимоги:
- Усе текстове наповнення українською.
- Якщо штрихкод (barcode) невідомий — поверни EAN-13 код найбільш схожого продукту з world.openfoodfacts.org
- Коди повинні бути реальними а не вигаданими чи не справжніми як 4820001000016', '4820002000022', '4820003000038'
- НЕ додавай нутрієнти.
- Поверни ТІЛЬКИ JSON без пояснень.
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

def _normalize_plan_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw LLM plan JSON into schema-compatible structure.

    Transforms keys:
    - day -> day_number
    - meal_type -> meal_title
    Ensures each dish has a nutrition list (may be empty) to satisfy DishItem schema.
    Ignores unknown fields gracefully.
    """
    days = data.get("days")
    if not isinstance(days, list):
        return data
    normalized_days: List[Dict[str, Any]] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        d: Dict[str, Any] = {}
        # Map day number
        if "day_number" in day:
            d["day_number"] = day.get("day_number")
        elif "day" in day:
            d["day_number"] = day.get("day")
        else:
            # fallback: sequential index starting at 1
            d["day_number"] = len(normalized_days) + 1

        meals = day.get("meals") if isinstance(day.get("meals"), list) else []
        normalized_meals: List[Dict[str, Any]] = []
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            m: Dict[str, Any] = {}
            if "meal_title" in meal:
                m["meal_title"] = meal.get("meal_title")
            elif "meal_type" in meal:
                m["meal_title"] = meal.get("meal_type")
            else:
                m["meal_title"] = ""  # will be normalized by validator
            dishes = meal.get("dishes") if isinstance(meal.get("dishes"), list) else []
            normalized_dishes: List[Dict[str, Any]] = []
            for dish in dishes:
                if not isinstance(dish, dict):
                    continue
                di: Dict[str, Any] = {}
                di["dish_title"] = dish.get("dish_title") or dish.get("title") or ""
                di["short_description"] = dish.get("short_description") or dish.get("description") or ""
                # Ensure nutrition list present
                nutrition = dish.get("nutrition")
                if not isinstance(nutrition, list):
                    nutrition = []
                # Normalize nutrition items if any present (sometimes LLM may include them despite prompt)
                norm_nutrition: List[Dict[str, Any]] = []
                for n in nutrition:
                    if isinstance(n, dict):
                        norm_nutrition.append({
                            "nutrition_title": n.get("nutrition_title") or n.get("title") or n.get("name", ""),
                            "value": n.get("value", 0),
                            "unit": n.get("unit", "")
                        })
                di["nutrition"] = norm_nutrition
                normalized_dishes.append(di)
            if normalized_dishes:
                m["dishes"] = normalized_dishes
                normalized_meals.append(m)
        if normalized_meals:
            d["meals"] = normalized_meals
            normalized_days.append(d)
    if normalized_days:
        data["days"] = normalized_days
    return data

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(0.5, 1.5))
async def _generate_meal_plan(req: MealPlanRequest) -> MealPlanResponse:
    log.step("meal_plan", "llm_plan.start", days=req.days, dishes=req.dishes_uk)
    plan_vars = {
        "days": req.days,
        "dishes_uk": ", ".join(req.dishes_uk) if req.dishes_uk else "(порожньо)",
        "allow_new_similar": str(bool(req.allow_new_similar)).lower(),
        "new_similar_ratio": req.new_similar_ratio,
        "user_message": (req.user_message or "").strip() or "(немає)"
    }
    _log_prompt("meal_plan", "llm_plan.prompt", PLAN_PROMPT, plan_vars)
    chain = PLAN_PROMPT | _llm() | json_parser
    data = await chain.ainvoke(plan_vars)
    # Normalize structure to current schema
    data = _normalize_plan_dict(data if isinstance(data, dict) else {})
    log.step("meal_plan", "llm_plan.done", keys=list(data.keys()))
    try:
        return MealPlanResponse(**data)
    except Exception as e:
        # Log the raw data for debugging before retrying
        log.exception("meal_plan", "llm_plan.validation_fail", detail=str(e), raw=data)
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(0.5, 1.5))
async def _enrich_with_nutrition(plan: MealPlanResponse) -> MealPlanResponse:
    log.step("meal_plan", "nutrition_enrich.start", dish_count=sum(len(m.dishes) for d in plan.days for m in d.meals))
    serialized = plan.model_dump(mode="json")
    vars_nutrition = {"plan_json": json.dumps(serialized, ensure_ascii=False)}
    _log_prompt("meal_plan", "nutrition.prompt", NUTRITION_PROMPT, vars_nutrition)
    chain = NUTRITION_PROMPT | _llm() | json_parser
    data = await chain.ainvoke(vars_nutrition)
    # Build map keyed only by dish title (LLM output currently lacks day info)
    nutrition_map: Dict[str, List[Dict[str, Any]]] = {}
    for item in data.get("items", []):
        if isinstance(item, dict):
            dish_title = item.get("dish_uk")
            if dish_title:
                nutrition_map[dish_title] = item.get("nutrition", [])

    # Assign nutrition by dish title match
    for day in plan.days:
        for meal in day.meals:
            for dish in meal.dishes:
                if dish.dish_title in nutrition_map:
                    dish.nutrition = [
                        NutritionItem(
                            nutrition_title=n.get("nutrition_title") or n.get("title") or n.get("name", ""),
                            value=float(n.get("value", 0) or 0),
                            unit=n.get("unit", "")
                        ) for n in nutrition_map[dish.dish_title] if isinstance(n, dict)
                    ]
    log.step("meal_plan", "nutrition_enrich.done")
    return plan

async def build_meal_plan(req: MealPlanRequest) -> MealPlanResponse:
    log.step("meal_plan", "build.start")
    plan = await _generate_meal_plan(req)
    plan = await _enrich_with_nutrition(plan)  # re-enabled enrichment (previously commented)
    log.step("meal_plan", "build.done", days=len(plan.days))
    return plan

async def _fetch_product_by_barcode(barcode: str) -> Dict[str, Any]:
    log.step("barcode", "fetch.start", barcode=barcode)
    cached = nutrition_kv.get(barcode)
    if cached:
        log.step("barcode", "fetch.cached", barcode=barcode)
        return cached

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json")
            resp.raise_for_status()
        except Exception as e:
            log.error("barcode", "fetch.error", barcode=barcode, error=repr(e))
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
    log.step("barcode", "fetch.done", barcode=barcode, nutrition_count=len(nutrition))
    return result

async def dish_info(dish_uk: str) -> DishInfoResponse:
    """Generate dish info using LLM then enrich with barcodes and nutrition via MCP.

    New expected LLM format:
    {
      "dish_title": "...",
      "short_description": "...",
      "short_recipe": "...",
      "recipe": "...",
      "ingredients": [ {"name": "інгредієнт", "barcode": "1234567890123"}, ... ]
    }

    Steps:
    1. Call LLM; parse ingredients list objects (name + optional barcode).
    2. Collect names missing barcode; resolve via MCP map tool.
    3. Persist caches and aggregate nutrition for resolved barcodes (fetch missing via MCP nutrition tool).
    4. Translate nutrition titles if needed.
    5. Return DishInfoResponse with IngredientItem list.
    """
    log.step("dish_info", "start", dish=dish_uk)

    # 1. LLM dish metadata
    vars_prompt = {"dish_uk": dish_uk}
    _log_prompt("dish_info", "prompt", DISH_INFO_PROMPT, vars_prompt)
    chain = DISH_INFO_PROMPT | _llm() | json_parser
    raw = await chain.ainvoke(vars_prompt)
    if not isinstance(raw, dict):
        raw = {"dish_title": dish_uk}

    dish_title = raw.get("dish_title") or dish_uk
    short_description = raw.get("short_description", "")
    short_recipe = raw.get("short_recipe", "")
    recipe = raw.get("recipe", "")

    # Parse ingredients list (new format); fallback: if legacy structure found
    ing_list_raw = raw.get("ingredients") or []
    ingredient_items: List[IngredientItem] = []
    if isinstance(ing_list_raw, list):
        for ing in ing_list_raw:
            if isinstance(ing, dict):
                name = str(ing.get("name", "")).strip()
                barcode_val = str(ing.get("barcode", "")).strip()
                if name:
                    ingredient_items.append(IngredientItem(uk=name, barcode=barcode_val))
    elif isinstance(ing_list_raw, dict):  # legacy support {"uk": [...], "en": [...]} but en ignored now
        uk_legacy = ing_list_raw.get("uk") or []
        if isinstance(uk_legacy, list):
            for name in uk_legacy:
                name_s = str(name).strip()
                if name_s:
                    ingredient_items.append(IngredientItem(uk=name_s, barcode=""))
    # Deduplicate by (uk, barcode) preserving order (case-insensitive name)
    seen_names: set[str] = set()
    deduped: List[IngredientItem] = []
    for it in ingredient_items:
        key = it.uk.lower()
        if key not in seen_names:
            seen_names.add(key)
            deduped.append(it)
    ingredient_items = deduped

    # print(ingredient_items)

    # 2. Resolve barcodes for missing ones via MCP & caching
    # names_to_lookup: List[str] = [it.uk for it in ingredient_items if not it.barcode]
    names_to_lookup: List[str] = [it.uk for it in ingredient_items if it.barcode]
    resolved_map: Dict[str, List[str]] = {}

    print(names_to_lookup)

    if names_to_lookup:
        log.step("dish_info", "barcode.lookup", count=len(names_to_lookup))
        mcp_client = MCPClient()
        found = await mcp_client.find_barcodes_for_names(names_to_lookup)
        # Fallback token logic for unresolved
        unresolved: List[str] = []
        for name, codes in found.items():
            norm_codes = [str(c).strip() for c in codes if str(c).strip()]
            if norm_codes:
                barcode_kv.set(name, norm_codes)
                resolved_map[name] = norm_codes
            else:
                unresolved.append(name)
                resolved_map[name] = []
        if unresolved:
            log.step("dish_info", "barcode.fallback.start", count=len(unresolved))
            token_queries: List[str] = []
            map_name_tokens: Dict[str, List[str]] = {}
            for name in unresolved:
                parts = [p for p in re.split(r"[\s,]+", name) if p]
                tokens: List[str] = []
                if parts:
                    tokens.append(parts[0])
                if len(parts) > 1:
                    tokens.append(parts[-1])
                uniq: List[str] = []
                for t in tokens:
                    if t.lower() not in [u.lower() for u in uniq]:
                        uniq.append(t)
                map_name_tokens[name] = uniq
                token_queries.extend(uniq)
            token_queries = list(dict.fromkeys(token_queries))
            if token_queries:
                found_tokens = await mcp_client.find_barcodes_for_names(token_queries)
                for ing_name, toks in map_name_tokens.items():
                    collected: List[str] = []
                    for tk in toks:
                        codes_for_token = found_tokens.get(tk) or []
                        for c in codes_for_token:
                            sc = str(c).strip()
                            if sc and sc not in collected:
                                collected.append(sc)
                        if collected:
                            break
                    if collected:
                        barcode_kv.set(ing_name, collected)
                        resolved_map[ing_name] = collected
            log.step("dish_info", "barcode.fallback.done")

    # Apply resolved primary barcode to items
    for it in ingredient_items:
        if not it.barcode:
            codes = resolved_map.get(it.uk, [])
            if codes:
                it.barcode = codes[0]

    # Collect list of barcodes for nutrition (skip empty)
    ordered_barcodes: List[str] = [it.barcode for it in ingredient_items if it.barcode]

    # 3. Fetch nutrition per barcode with caching & MCP only for missing
    missing_barcodes = [b for b in ordered_barcodes if not nutrition_kv.get(b)]
    nutrition_items_agg: List[NutritionItem] = []

    print(missing_barcodes)

    if missing_barcodes:
        log.step("dish_info", "nutrition.lookup", count=len(missing_barcodes))
        mcp_client2 = MCPClient()
        analyzed = await mcp_client2.analyze_nutrition(missing_barcodes)
        for b, data in analyzed.items():
            nutrition_kv.set(b, data)

    # Aggregate nutrition
    for b in ordered_barcodes:
        entry = nutrition_kv.get(b) or {}
        n_list = entry.get("nutrition") or []
        for n in n_list:
            if isinstance(n, dict):
                title = n.get("nutrition_title") or n.get("title") or n.get("name") or ""
                value = n.get("value") or n.get("amount") or 0
                unit = n.get("unit") or n.get("u") or ""
                try:
                    value_f = float(value)
                except Exception:
                    value_f = 0.0
                nutrition_items_agg.append(NutritionItem(nutrition_title=title, value=value_f, unit=unit))

    # 4. Translate nutrition titles if needed
    def _is_uk(text: str) -> bool:
        return bool(re.search(r"[А-Яа-яІіЇїЄєҐґ]", text))
    needs_translation = any(not _is_uk(n.nutrition_title) for n in nutrition_items_agg)
    if needs_translation and nutrition_items_agg:
        trans_prompt = ChatPromptTemplate.from_messages([
            ("system", """Переклади назви нутрієнтів на українську. Поверни СТРОГО JSON:
{
  "nutrition": [
    {"nutrition_title": "Калорії", "value": 350, "unit": "kcal"}
  ]
}
Не змінюй value і unit.
"""),
            ("human", "Ось JSON нутрієнтів англійською: {nutrition_json}")
        ])
        payload = {"nutrition": [n.model_dump(mode="json") for n in nutrition_items_agg]}
        chain_trans = trans_prompt | _llm() | json_parser
        translated = await chain_trans.ainvoke({"nutrition_json": json.dumps(payload, ensure_ascii=False)})
        nut_out = translated.get("nutrition") if isinstance(translated, dict) else None
        if isinstance(nut_out, list):
            new_items: List[NutritionItem] = []
            for n in nut_out:
                if isinstance(n, dict):
                    new_items.append(NutritionItem(
                        nutrition_title=n.get("nutrition_title") or n.get("title") or n.get("name", ""),
                        value=float(n.get("value", 0) or 0),
                        unit=n.get("unit", "")
                    ))
            if new_items:
                nutrition_items_agg = new_items
                log.step("dish_info", "nutrition.translated", count=len(new_items))

    # 5. Deduplicate nutrition (title+unit)
    merged: Dict[tuple, float] = {}
    for n in nutrition_items_agg:
        key = (n.nutrition_title.lower().strip(), n.unit.lower().strip())
        merged[key] = merged.get(key, 0.0) + n.value
    dedup_items = [NutritionItem(nutrition_title=k[0], value=v, unit=k[1]) for k, v in merged.items()]

    log.step("dish_info", "done", dish=dish_title, ingredients=len(ingredient_items), barcodes=len(ordered_barcodes), nutrition_count=len(dedup_items))
    return DishInfoResponse(
        dish_title=dish_title,
        short_description=short_description,
        short_recipe=short_recipe,
        recipe=recipe,
        ingredients=ingredient_items,
        nutrition=dedup_items
    )
