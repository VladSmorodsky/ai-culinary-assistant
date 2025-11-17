#!/usr/bin/env python3
"""
Test script for the nutrition MCP server.
This script tests the MCP server by calling it directly.
"""

import asyncio
import json
from app.core.mcp_client import MCPClient


async def test_nutrition_mcp():
    """Test the nutrition MCP server with sample ingredients."""
    print("Testing Nutrition MCP Server...")
    print("=" * 60)

    # Test ingredients with quantities
    test_ingredients = ["1 cup rice", "100g chicken breast", "medium apple"]

    print(f"\nTest ingredients: {test_ingredients}\n")

    try:
        # Create MCP client
        client = MCPClient()

        # Call the nutrition MCP server
        print("Calling MCP server...")
        result = await client.get_nutrition_for_ingredients(test_ingredients)

        # Display results
        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Summary
        ingredients_data = result.get("ingredients", [])
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)

        for ing_data in ingredients_data:
            if isinstance(ing_data, dict):
                ingredient = ing_data.get("ingredient", "Unknown")

                if "error" in ing_data:
                    print(f"\n❌ {ingredient}")
                    print(f"   Error: {ing_data['error']}")
                else:
                    calories = ing_data.get("calories", 0)
                    weight = ing_data.get("totalWeight", 0)
                    nutrients = ing_data.get("nutrients", {})

                    print(f"\n✅ {ingredient}")
                    print(f"   Calories: {calories} kcal")
                    print(f"   Weight: {weight}g")
                    print(f"   Nutrients: {len(nutrients)} items")

                    # Show key nutrients
                    if nutrients:
                        print("   Key nutrients:")
                        for name, data in list(nutrients.items())[:5]:
                            if isinstance(data, dict):
                                qty = data.get("quantity", 0)
                                unit = data.get("unit", "")
                                print(f"     - {name}: {qty:.2f} {unit}")

        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")

    except Exception as e:
        print(f"\n❌ Error testing MCP server: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_nutrition_mcp())
