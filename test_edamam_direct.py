#!/usr/bin/env python3
"""Direct test of Edamam Food Database API with proper extraction."""

import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

EDAMAM_APP_ID = os.getenv("EDAMAM_APP_ID", "")
EDAMAM_APP_KEY = os.getenv("EDAMAM_APP_KEY", "")
EDAMAM_FOOD_DATABASE_URL = "https://api.edamam.com/api/food-database/v2/parser"


async def fetch_nutrition_data(ingredient: str) -> dict:
    """Test the same logic as the MCP server."""
    if not EDAMAM_APP_ID or not EDAMAM_APP_KEY:
        return {"ingredient": ingredient, "error": "Credentials not set"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Search for the food item
            search_params = {
                "app_id": EDAMAM_APP_ID,
                "app_key": EDAMAM_APP_KEY,
                "ingr": ingredient,
                "nutrition-type": "cooking",
            }

            response = await client.get(EDAMAM_FOOD_DATABASE_URL, params=search_params)
            response.raise_for_status()
            data = response.json()

            # Get the first parsed item or hint
            parsed_items = data.get("parsed", [])
            if not parsed_items:
                hints = data.get("hints", [])
                if not hints:
                    return {"ingredient": ingredient, "error": "No food items found"}
                food_data = hints[0].get("food", {})
            else:
                food_data = parsed_items[0].get("food", {})

            # Extract nutrients
            nutrients = food_data.get("nutrients", {})
            calories = nutrients.get("ENERC_KCAL", 0)

            # Build structured response
            nutrition_info = {
                "ingredient": ingredient,
                "food_label": food_data.get("label", ingredient),
                "calories": round(calories, 2),
                "totalWeight": 100,
                "totalWeightUnit": "g",
                "nutrients": {},
            }

            # Extract key nutrients
            nutrient_mapping = {
                "ENERC_KCAL": ("energy", "kcal"),
                "FAT": ("fat", "g"),
                "FASAT": ("saturated_fat", "g"),
                "CHOCDF": ("carbohydrates", "g"),
                "FIBTG": ("fiber", "g"),
                "SUGAR": ("sugars", "g"),
                "PROCNT": ("protein", "g"),
                "CHOLE": ("cholesterol", "mg"),
                "NA": ("sodium", "mg"),
                "CA": ("calcium", "mg"),
                "MG": ("magnesium", "mg"),
                "K": ("potassium", "mg"),
                "FE": ("iron", "mg"),
                "ZN": ("zinc", "mg"),
            }

            for edamam_code, (friendly_name, unit) in nutrient_mapping.items():
                if edamam_code in nutrients:
                    value = nutrients[edamam_code]
                    if isinstance(value, (int, float)) and value > 0:
                        nutrition_info["nutrients"][friendly_name] = {
                            "quantity": round(float(value), 2),
                            "unit": unit,
                        }

            return nutrition_info

    except Exception as e:
        return {"ingredient": ingredient, "error": str(e)}


async def main():
    print("🧪 Testing Edamam Food Database API Integration")
    print("=" * 70)

    test_ingredients = ["rice", "apple", "chicken breast"]

    for ingredient in test_ingredients:
        print(f"\n📋 Testing: {ingredient}")
        result = await fetch_nutrition_data(ingredient)

        if "error" in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print("   ✅ Success!")
            print(f"   Food Label: {result.get('food_label')}")
            print(f"   Calories: {result.get('calories')} kcal (per 100g)")

            nutrients = result.get("nutrients", {})
            print(f"   Nutrients Found: {len(nutrients)} items")

            if nutrients:
                print("\n   📊 Nutrient Breakdown:")
                for name, data in nutrients.items():
                    qty = data.get("quantity", 0)
                    unit = data.get("unit", "")
                    print(f"      • {name:20s}: {qty:>8.2f} {unit}")

    print("\n" + "=" * 70)
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
