#!/usr/bin/env python3
"""
MCP Server for Nutrition Information using Edamam API.
This server provides a tool to get nutrition information for ingredients.
"""

from __future__ import annotations
import asyncio
import json
import os
from typing import Any
import httpx

try:
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions, Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: mcp package not installed. Run: pip install mcp")
    exit(1)


# Edamam API configuration
EDAMAM_APP_ID = os.getenv("EDAMAM_APP_ID", "")
EDAMAM_APP_KEY = os.getenv("EDAMAM_APP_KEY", "")
EDAMAM_FOOD_DATABASE_URL = "https://api.edamam.com/api/food-database/v2/parser"
EDAMAM_NUTRIENTS_URL = "https://api.edamam.com/api/food-database/v2/nutrients"


# Create MCP server instance
server = Server("nutrition-edamam")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_nutrition_info",
            description=(
                "Get nutrition information for ingredients using Edamam Food Database API. "
                "Takes ingredient names and returns detailed nutrition data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ingredient names (e.g., ['rice', 'apple', 'chicken breast'])",
                    }
                },
                "required": ["ingredients"],
            },
        )
    ]


async def fetch_nutrition_data(ingredient: str) -> dict[str, Any]:
    """
    Fetch nutrition data for a single ingredient from Edamam Food Database API.

    This uses a two-step process:
    1. Search for the food item using the parser API
    2. Get detailed nutrition data using the nutrients API

    Args:
        ingredient: Ingredient description (e.g., "rice", "apple", "chicken breast")

    Returns:
        Dictionary with nutrition information
    """
    if not EDAMAM_APP_ID or not EDAMAM_APP_KEY:
        return {
            "ingredient": ingredient,
            "error": "Edamam API credentials not configured. Set EDAMAM_APP_ID and EDAMAM_APP_KEY.",
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: Search for the food item
            search_params = {
                "app_id": EDAMAM_APP_ID,
                "app_key": EDAMAM_APP_KEY,
                "ingr": ingredient,
                "nutrition-type": "cooking",
            }

            search_response = await client.get(
                EDAMAM_FOOD_DATABASE_URL, params=search_params
            )
            search_response.raise_for_status()
            search_data = search_response.json()

            # Get the first parsed item
            parsed_items = search_data.get("parsed", [])
            if not parsed_items:
                # Try hints if no parsed results
                hints = search_data.get("hints", [])
                if not hints:
                    return {
                        "ingredient": ingredient,
                        "error": "No food items found for this ingredient",
                    }
                # Use first hint
                food_data = hints[0].get("food", {})
            else:
                food_data = parsed_items[0].get("food", {})

            # Step 2: Get nutrition data
            # For Food Database API, we can use the nutrients from the food object directly
            nutrients = food_data.get("nutrients", {})

            # Extract calories and weight (default serving size)
            calories = nutrients.get("ENERC_KCAL", 0)
            # For food database, weight is per 100g by default
            total_weight = 100

            # Build structured nutrition response
            nutrition_info = {
                "ingredient": ingredient,
                "calories": calories,
                "totalWeight": total_weight,
                "totalWeightUnit": "g",
                "nutrients": {},
            }

            # Extract key nutrients with friendly names
            # Food Database API returns nutrients as direct numeric values (per 100g)
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
                "VITA_RAE": ("vitamin_a", "µg"),
                "VITC": ("vitamin_c", "mg"),
                "VITD": ("vitamin_d", "µg"),
                "VITB12": ("vitamin_b12", "µg"),
            }

            for edamam_code, (friendly_name, unit) in nutrient_mapping.items():
                if edamam_code in nutrients:
                    value = nutrients[edamam_code]
                    # Food Database API returns nutrients as direct numeric values
                    if isinstance(value, (int, float)) and value > 0:
                        nutrition_info["nutrients"][friendly_name] = {
                            "quantity": round(float(value), 2),
                            "unit": unit,
                        }

            return nutrition_info

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {
                "ingredient": ingredient,
                "error": "No nutrition data found. Try being more specific with quantity (e.g., '1 cup' or '100g').",
            }
        return {
            "ingredient": ingredient,
            "error": f"API error: {e.response.status_code}",
        }
    except httpx.TimeoutException:
        return {"ingredient": ingredient, "error": "Request timed out"}
    except Exception as e:
        return {
            "ingredient": ingredient,
            "error": f"Failed to fetch nutrition data: {str(e)}",
        }


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Handle tool calls."""
    if name != "get_nutrition_info":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments:
        return [
            TextContent(
                type="text", text=json.dumps({"error": "No arguments provided"})
            )
        ]

    ingredients = arguments.get("ingredients", [])

    if not isinstance(ingredients, list):
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "ingredients must be a list of strings"}),
            )
        ]

    if not ingredients:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "ingredients list cannot be empty"}),
            )
        ]

    # Fetch nutrition data for all ingredients concurrently
    tasks = [fetch_nutrition_data(ingredient) for ingredient in ingredients]
    results = await asyncio.gather(*tasks)

    # Build response with all ingredient nutrition data
    response = {"ingredients": results, "total_count": len(results)}

    return [TextContent(type="text", text=json.dumps(response, indent=2))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nutrition-edamam",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
