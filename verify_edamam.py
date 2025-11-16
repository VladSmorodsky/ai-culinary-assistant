#!/usr/bin/env python3
"""
Simple verification script to test Edamam API connection.
This doesn't require the MCP package - just tests the API directly.
"""

import asyncio
import os
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

EDAMAM_APP_ID = os.getenv("EDAMAM_APP_ID", "")
EDAMAM_APP_KEY = os.getenv("EDAMAM_APP_KEY", "")
EDAMAM_NUTRITION_API_URL = "https://api.edamam.com/api/food-database/v2/parser"


async def test_edamam_api():
    """Test Edamam API directly without MCP."""
    print("🔍 Verifying Edamam API Connection")
    print("=" * 60)

    # Check credentials
    if not EDAMAM_APP_ID or not EDAMAM_APP_KEY:
        print("❌ Edamam credentials not found!")
        print("   Please set EDAMAM_APP_ID and EDAMAM_APP_KEY in your .env file")
        return False

    print("✅ Credentials found:")
    print(f"   App ID: {EDAMAM_APP_ID[:4]}...{EDAMAM_APP_ID[-4:]}")
    print(f"   App Key: {EDAMAM_APP_KEY[:4]}...{EDAMAM_APP_KEY[-4:]}")
    print()

    # Test ingredients
    test_cases = ["1 cup rice", "medium apple", "100g chicken breast"]

    print("🥗 Testing ingredients:")
    print("-" * 60)

    success_count = 0
    for ingredient in test_cases:
        print(f"\n📋 Testing: {ingredient}")

        params = {
            "app_id": EDAMAM_APP_ID,
            "app_key": EDAMAM_APP_KEY,
            "ingr": ingredient,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(EDAMAM_NUTRITION_API_URL, params=params)
                response.raise_for_status()
                data = response.json()

                calories = data.get("calories", 0)
                weight = data.get("totalWeight", 0)
                nutrients = data.get("totalNutrients", {})

                print("   ✅ Success!")
                print(f"   📊 Calories: {calories} kcal")
                print(f"   ⚖️  Weight: {weight}g")
                print(f"   🥗 Nutrients: {len(nutrients)} items")

                # Show a few key nutrients
                if "PROCNT" in nutrients:
                    protein = nutrients["PROCNT"]
                    print(
                        f"   💪 Protein: {protein.get('quantity', 0):.1f} {protein.get('unit', '')}"
                    )
                if "CHOCDF" in nutrients:
                    carbs = nutrients["CHOCDF"]
                    print(
                        f"   🍞 Carbs: {carbs.get('quantity', 0):.1f} {carbs.get('unit', '')}"
                    )
                if "FAT" in nutrients:
                    fat = nutrients["FAT"]
                    print(
                        f"   🧈 Fat: {fat.get('quantity', 0):.1f} {fat.get('unit', '')}"
                    )

                success_count += 1

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print("   ⚠️  No nutrition data found")
                print("   💡 Tip: Try being more specific with quantity")
            elif e.response.status_code == 401:
                print("   ❌ Authentication failed!")
                print("   💡 Check your Edamam credentials")
                return False
            elif e.response.status_code == 403:
                print("   ❌ Access forbidden!")
                print("   💡 Check if your API plan allows this endpoint")
                return False
            else:
                print(f"   ❌ API error: {e.response.status_code}")
        except httpx.TimeoutException:
            print("   ❌ Request timed out")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n" + "=" * 60)
    print(f"📊 Results: {success_count}/{len(test_cases)} ingredients successful")

    if success_count == len(test_cases):
        print("✅ All tests passed! Edamam API is working correctly.")
        return True
    elif success_count > 0:
        print("⚠️  Some tests passed. API is working but some ingredients failed.")
        return True
    else:
        print("❌ All tests failed. Please check your credentials.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_edamam_api())
    exit(0 if success else 1)
