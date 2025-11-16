#!/usr/bin/env python3
"""
Direct test of the nutrition MCP server using stdio communication.
This simulates how the MCPClient communicates with the server.
"""

import asyncio
import json
import os
import sys

# Set environment variables for testing
os.environ["EDAMAM_APP_ID"] = os.getenv("EDAMAM_APP_ID", "")
os.environ["EDAMAM_APP_KEY"] = os.getenv("EDAMAM_APP_KEY", "")


async def test_mcp_server_direct():
    """Test MCP server by spawning it as a subprocess."""
    from mcp.client.stdio import stdio_client, StdioServerParameters

    print("🧪 Testing Nutrition MCP Server (Direct)")
    print("=" * 60)

    # Check credentials
    if not os.getenv("EDAMAM_APP_ID") or not os.getenv("EDAMAM_APP_KEY"):
        print("⚠️  WARNING: Edamam credentials not set!")
        print("   Set EDAMAM_APP_ID and EDAMAM_APP_KEY environment variables")
        print("   or add them to your .env file")
        return

    # Server parameters - pass environment variables to subprocess
    server_params = StdioServerParameters(
        command="python3",
        args=["app/core/nutrition_mcp_client.py"],
        env=dict(os.environ),
    )

    print(
        f"\n📡 Starting MCP server: {server_params.command} {' '.join(server_params.args)}"
    )

    try:
        # Connect to server
        async with stdio_client(server_params) as (read, write):
            from mcp import ClientSession

            async with ClientSession(read, write) as session:
                # Initialize session
                print("🔄 Initializing MCP session...")
                await session.initialize()
                print("✅ Connected to MCP server")

                # List available tools
                print("\n🔧 Listing available tools...")
                tools_result = await session.list_tools()
                tools = tools_result.tools if hasattr(tools_result, "tools") else []

                print(f"   Found {len(tools)} tool(s):")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description}")

                # Test the nutrition tool
                test_ingredients = ["1 cup rice", "medium apple", "100g chicken breast"]
                print(f"\n🥗 Testing with ingredients: {test_ingredients}")

                result = await session.call_tool(
                    "get_nutrition_info", {"ingredients": test_ingredients}
                )

                print("\n📊 Results:")
                print("=" * 60)

                if result.content:
                    for content in result.content:
                        if hasattr(content, "text"):
                            data = json.loads(content.text)
                            print(json.dumps(data, indent=2, ensure_ascii=False))

                            # Summary
                            ingredients_data = data.get("ingredients", [])
                            print("\n📈 Summary:")
                            print("-" * 60)

                            for ing in ingredients_data:
                                if "error" in ing:
                                    print(
                                        f"❌ {ing.get('ingredient')}: {ing.get('error')}"
                                    )
                                else:
                                    print(f"✅ {ing.get('ingredient')}:")
                                    print(f"   Calories: {ing.get('calories', 0)} kcal")
                                    print(f"   Weight: {ing.get('totalWeight', 0)}g")
                                    nutrients = ing.get("nutrients", {})
                                    print(f"   Nutrients: {len(nutrients)} items")

                print("\n" + "=" * 60)
                print("✅ Test completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_mcp_server_direct())
