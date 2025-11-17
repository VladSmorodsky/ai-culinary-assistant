# Testing the Nutrition MCP Server

This guide shows you how to verify that the nutrition MCP server is working correctly.

## Prerequisites

1. **Edamam API Credentials**: Make sure your `.env` file has valid credentials:
   ```bash
   EDAMAM_APP_ID="your_app_id"
   EDAMAM_APP_KEY="your_app_key"
   ```

   Get your free credentials from: https://www.edamam.com/

2. **Dependencies Installed**:

   **Option A - Local (without Docker):**
   ```bash
   source .venv/bin/activate
   pip install httpx python-dotenv
   ```

   **Option B - Docker:**
   ```bash
   docker-compose up --build
   ```

## Quick Start - Recommended Tests

### ⚡ Fastest Test (No MCP package required)

Test the Edamam API integration directly:

```bash
source .venv/bin/activate
python3 test_edamam_direct.py
```

**Expected Output:**
```
🧪 Testing Edamam Food Database API Integration
======================================================================

📋 Testing: rice
   ✅ Success!
   Food Label: Rice
   Calories: 360.0 kcal (per 100g)
   Nutrients Found: 4 items

   📊 Nutrient Breakdown:
      • energy              :   360.00 kcal
      • fat                 :     0.58 g
      • carbohydrates       :    79.30 g
      • protein             :     6.61 g

📋 Testing: apple
   ✅ Success!
   Food Label: Apple
   Calories: 52.0 kcal (per 100g)
   Nutrients Found: 5 items

   📊 Nutrient Breakdown:
      • energy              :    52.00 kcal
      • fat                 :     0.17 g
      • carbohydrates       :    13.80 g
      • fiber               :     2.40 g
      • protein             :     0.26 g

======================================================================
✅ All tests completed!
```

### 🔍 API Credentials Verification

Verify your Edamam credentials work:

```bash
source .venv/bin/activate
python3 verify_edamam.py
```

This will test the API connection and show if credentials are valid.

## All Available Test Methods

### Method 1: Direct API Test (Recommended - No Docker)

**Best for**: Quick testing without Docker or MCP package

```bash
source .venv/bin/activate
python3 test_edamam_direct.py
```

✅ Tests the core nutrition data fetching logic
✅ No MCP package installation needed
✅ Shows actual API response data
✅ Fastest test to run

### Method 2: Full MCP Server Test (Docker)

**Best for**: Testing the complete integration in Docker

```bash
# Start Docker containers
docker-compose up -d

# Run test inside Docker container
docker exec -it meal-assistant python3 test_mcp_direct.py
```

✅ Tests full MCP server communication
✅ Tests in production-like environment
✅ Verifies Docker configuration

### Method 3: Automated Test Script

**Best for**: CI/CD or automated testing

```bash
./test_simple.sh
```

This script:
- Starts Docker if not running
- Runs MCP server tests
- Shows detailed results

### Method 4: MCP Client Test (Requires MCP package)

**Best for**: Testing via the MCPClient interface

```bash
python3 test_nutrition_mcp.py
```

⚠️ **Note**: Requires `mcp` package to be installed

### Method 5: Test Through the API (End-to-End)

**Best for**: Testing the complete application flow

```bash
# Start the application
docker-compose up

# In another terminal, call the dish info endpoint
curl -X POST http://localhost:8000/api/dish-info \
  -H "Content-Type: application/json" \
  -d '{"dish_uk": "Борщ"}'
```

The response should include nutrition data with Ukrainian translations.

### Method 6: Manual Test in Python REPL

```python
import asyncio
import os
from app.core.mcp_client import MCPClient

# Set credentials (if not in .env)
os.environ["EDAMAM_APP_ID"] = "your_app_id"
os.environ["EDAMAM_APP_KEY"] = "your_app_key"
os.environ["MCP_SERVER_CMD"] = "python3"
os.environ["MCP_SERVER_ARGS"] = "/app/app/core/nutrition_mcp_client.py"
os.environ["NUTRITION_TOOL_NAME"] = "get_nutrition_info"

async def test():
    client = MCPClient()
    result = await client.get_nutrition_for_ingredients(["1 cup rice"])
    print(result)

asyncio.run(test())
```

## Test Summary Matrix

| Test Method | Docker Required | MCP Package Required | Speed | Best Use Case |
|-------------|----------------|---------------------|-------|---------------|
| `test_edamam_direct.py` | ❌ | ❌ | ⚡⚡⚡ | Quick local testing |
| `verify_edamam.py` | ❌ | ❌ | ⚡⚡⚡ | Credential verification |
| `test_mcp_direct.py` (Docker) | ✅ | ✅ | ⚡⚡ | Full integration test |
| `test_simple.sh` | ✅ | ✅ | ⚡⚡ | Automated testing |
| API endpoint | ✅ | ✅ | ⚡ | End-to-end testing |

## Troubleshooting

### Error: "Edamam API credentials not configured"

**Solution**: Add your credentials to `.env`:
```bash
EDAMAM_APP_ID="your_app_id"
EDAMAM_APP_KEY="your_app_key"
```

**If running in Docker**: After updating `.env`, restart the container:
```bash
docker-compose down
docker-compose up -d
```

Verify credentials are loaded in Docker:
```bash
docker exec meal-assistant env | grep EDAMAM
```

### Error: "MCP_SERVER_CMD is not set"

**Solution**: Ensure your `.env` file has:
```bash
MCP_SERVER_CMD=python3
MCP_SERVER_ARGS="/app/app/core/nutrition_mcp_client.py"
NUTRITION_TOOL_NAME="get_nutrition_info"
```

### Error: "No nutrition data found"

**Possible causes:**
1. Ingredient needs more specific quantity (e.g., "rice" → "1 cup rice")
2. Ingredient name not recognized by Edamam
3. API rate limit reached

**Solution**: Try with different ingredient format or check Edamam API status.

### Error: "Module mcp not found"

**Solution**: Install dependencies:
```bash
poetry install
# or
pip install mcp
```

## Verify in Logs

When the application runs, you should see logs like:

```
[dish_info] nutrition.edamam.start count=3
[dish_info] nutrition.edamam.done count=15
```

This indicates the Edamam MCP server is being called and returning data.

## Expected Nutrition Data Format

### MCP Server Output Format

The MCP server returns data per 100g:

```json
{
  "ingredients": [
    {
      "ingredient": "rice",
      "food_label": "Rice",
      "calories": 360.0,
      "totalWeight": 100,
      "totalWeightUnit": "g",
      "nutrients": {
        "energy": {"quantity": 360.0, "unit": "kcal"},
        "protein": {"quantity": 6.61, "unit": "g"},
        "fat": {"quantity": 0.58, "unit": "g"},
        "carbohydrates": {"quantity": 79.3, "unit": "g"},
        "fiber": {"quantity": 2.4, "unit": "g"},
        "calcium": {"quantity": 10.0, "unit": "mg"},
        "iron": {"quantity": 1.2, "unit": "mg"}
      }
    }
  ],
  "total_count": 1
}
```

### Agent Output (with Ukrainian translation)

In the application, these become:

```json
{
  "nutrition": [
    {"nutrition_title": "Калорії", "value": 360.0, "unit": "kcal"},
    {"nutrition_title": "Білки", "value": 6.61, "unit": "g"},
    {"nutrition_title": "Жири", "value": 0.58, "unit": "g"},
    {"nutrition_title": "Вуглеводи", "value": 79.3, "unit": "g"}
  ]
}
```

## Success Indicators

✅ MCP server starts without errors
✅ Tools are listed correctly
✅ Nutrition data is returned for valid ingredients
✅ Ukrainian translations are applied in the agent
✅ No timeout errors
✅ Calories and nutrients are populated

## Recommended Testing Workflow

### 1️⃣ First Time Setup

```bash
# 1. Clone and navigate to project
cd ai-culinary-assistant

# 2. Set up credentials in .env
nano .env
# Add your EDAMAM_APP_ID and EDAMAM_APP_KEY

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install minimal dependencies
pip install httpx python-dotenv
```

### 2️⃣ Quick Validation

```bash
# Test 1: Verify credentials work
python3 verify_edamam.py

# Test 2: Test nutrition data extraction
python3 test_edamam_direct.py
```

### 3️⃣ Full Integration Test

```bash
# Build and start Docker (restart to pick up .env changes)
docker-compose down
docker-compose up --build -d

# Run integration test
docker exec meal-assistant python3 test_mcp_direct.py

# Check logs
docker-compose logs -f assistant
```

### 4️⃣ End-to-End Test

```bash
# Test via API endpoint
curl -X POST http://localhost:8000/api/dish-info \
  -H "Content-Type: application/json" \
  -d '{"dish_uk": "Борщ"}' | jq
```

## Next Steps

If all tests pass, the MCP server is ready to use in production!

You can now:
1. ✅ Start the application: `docker-compose up`
2. ✅ Make API calls to get dish information with nutrition data
3. ✅ Monitor logs for nutrition data being fetched
4. ✅ Integration is complete!

## Support & Documentation

- **Edamam API Docs**: https://developer.edamam.com/food-database-api-docs
- **MCP Protocol**: https://github.com/modelcontextprotocol/
- **Project Issues**: Create an issue if you encounter problems

---

**Last Updated**: 2025-01-16
**API Version**: Edamam Food Database v2
**MCP Version**: 1.21.0
