#!/usr/bin/env python3
"""Simple test of the nutrition MCP server fetch function."""

import asyncio
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.nutrition_mcp_client import fetch_nutrition_data


async def test():
    print("Testing nutrition data fetching...")
    print("=" * 60)

    test_ingredients = ["rice", "apple", "chicken breast"]

    for ingredient in test_ingredients:
        print(f"\n📋 Testing: {ingredient}")
        result = await fetch_nutrition_data(ingredient)

        if "error" in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print("   ✅ Success!")
            print(f"   Food: {result.get('ingredient')}")
            print(f"   Calories: {result.get('calories', 0)} kcal")
            print(f"   Weight: {result.get('totalWeight', 0)}g")

            nutrients = result.get("nutrients", {})
            print(f"   Nutrients: {len(nutrients)} items")

            # Show first 5 nutrients
            for i, (name, data) in enumerate(list(nutrients.items())[:5]):
                qty = data.get("quantity", 0)
                unit = data.get("unit", "")
                print(f"      - {name}: {qty} {unit}")

    print("\n" + "=" * 60)
    print("✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(test())
