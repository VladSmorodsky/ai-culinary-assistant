#!/bin/bash
# Simple test script to verify MCP server works in Docker

echo "🧪 Testing Nutrition MCP Server in Docker"
echo "=========================================="
echo ""

# Check if docker-compose is running
if ! docker ps | grep -q meal-assistant; then
    echo "⚠️  Container 'meal-assistant' is not running"
    echo "   Starting containers..."
    docker-compose up -d
    echo "   Waiting for container to be ready..."
    sleep 5
fi

echo "📡 Running MCP server test..."
echo ""

# Run the test inside Docker
docker exec meal-assistant python3 test_mcp_direct.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
else
    echo ""
    echo "❌ Tests failed with exit code: $exit_code"
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "   1. Check if Edamam credentials are set in .env"
    echo "   2. View container logs: docker-compose logs assistant"
    echo "   3. Check if MCP package is installed: docker exec meal-assistant pip list | grep mcp"
fi

exit $exit_code
