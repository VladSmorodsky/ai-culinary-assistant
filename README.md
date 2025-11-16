# AI Culinary Assistant

A FastAPI-based AI culinary assistant application with PostgreSQL and Redis support, powered by OpenAI and integrated with Edamam Nutrition API.

## Features

- FastAPI web framework with async support
- OpenAI integration for intelligent meal planning and dish information
- Nutrition data integration via Edamam Food Database API
- Model Context Protocol (MCP) server for nutrition data fetching
- PostgreSQL database for data persistence
- Redis for caching and session management
- Docker containerization with docker-compose
- Pre-commit hooks for code quality
- Ruff for linting and formatting
- Poetry for dependency management

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Poetry (for local development)
- Edamam API credentials (free tier available at https://www.edamam.com/)
- OpenAI API key

## Quick Start with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-culinary-assistant
```

2. Copy the environment file and configure it:
```bash
cp .env.example .env
# Edit .env with your configuration:
# - OPENAI_API_KEY: Your OpenAI API key
# - EDAMAM_APP_ID: Your Edamam application ID
# - EDAMAM_APP_KEY: Your Edamam application key
# - DATABASE_URL, REDIS_URL, etc.
```

3. Start all services:
```bash
docker-compose up -d
```

4. Access the application:
- API: http://localhost:8000
- API Documentation (Swagger UI): http://localhost:8000/docs
- API Documentation (ReDoc): http://localhost:8000/redoc

5. View logs:
```bash
docker-compose logs -f web
```

6. Stop services:
```bash
docker-compose down
```

## Local Development Setup

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Poetry

```bash
pip install poetry
```

### 3. Install Dependencies

```bash
poetry install
```

### 4. Configure Environment

For local development (outside Docker):
```bash
cp .env.local.example .env
# Edit .env to use localhost instead of service names
```

### 5. Set Up Pre-commit Hooks

```bash
pre-commit install
```

### 6. Run the Application Locally

Make sure PostgreSQL and Redis are running locally, then:

```bash
uvicorn app.main:app --reload
```

## docker-compose.override.yml

This repository includes a `docker-compose.override.yml` used only for local development. It adds:

- `container_name` (so you see a friendly name locally)
- `ports` mapping `8000:8000` to access the FastAPI app

The base `docker-compose.yml` intentionally uses `expose` instead of `ports` to avoid public bindings and port conflicts in managed environments like Easypanel.

Local usage (Compose automatically loads the override file):
```bash
docker compose up -d
```

If you want to ignore the override (simulate production/Easypanel):
```bash
docker compose -f docker-compose.yml up -d
```

## Deploying on Easypanel / VPS

When deploying to Easypanel:

- Upload only `docker-compose.yml` (omit `docker-compose.override.yml`)
- Easypanel will manage port publishing; since we only `expose: 8000`, it can assign or map without conflicts
- Do NOT include `container_name` or manual `ports` in production to prevent collisions with other apps

If Easypanel requires an external port, configure it in the panel UI rather than adding `ports:` in compose.

## Project Structure

```
ai-culinary-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Configuration and settings
│   │   ├── agent.py                 # AI agent implementation
│   │   ├── schemas.py               # Pydantic data models
│   │   ├── mcp_client.py            # MCP client for nutrition data
│   │   ├── nutrition_mcp_client.py  # MCP server for Edamam API
│   │   └── log_agent.py             # Logging utilities
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py            # API v1 routes
│   ├── models/                      # Database models
│   ├── schemas/                     # Additional schemas
│   └── services/                    # Business logic
├── data/
│   └── nutrition.json               # Nutrition translation data
├── test_mcp_direct.py               # MCP server integration test
├── test_edamam_direct.py            # Direct Edamam API test
├── verify_edamam.py                 # Credential verification
├── TEST_MCP_SERVER.md               # Testing documentation
├── .env                             # Environment variables (not in git)
├── .env.example                     # Example env file for Docker
├── .env.local.example               # Example env file for local development
├── docker-compose.yml               # Docker Compose configuration
├── docker-compose.override.yml # Local-only overrides (do not deploy)
├── Dockerfile                       # Docker image definition
├── pyproject.toml                   # Poetry dependencies
├── poetry.lock                      # Locked dependencies
├── .pre-commit-config.yaml          # Pre-commit hooks configuration
└── README.md
```

## API Endpoints

### Root
- `GET /` - Welcome message and API information

### Health
- `GET /health` - Health check endpoint

### API v1

#### Meal Planning
- `POST /api/v1/meal-plan` - Generate a personalized meal plan
  - Request body:
    ```json
    {
      "days": 7,
      "dishes_uk": ["Борщ", "Вареники"],
      "allow_new_similar": true,
      "new_similar_ratio": 0.3
    }
    ```
  - Returns: Structured meal plan with dishes for each day

#### Dish Information
- `POST /api/v1/dish-info` - Get detailed information about a dish
  - Request body:
    ```json
    {
      "dish_uk": "Борщ"
    }
    ```
  - Returns: Dish details including ingredients with nutrition data

#### Assistant Chat
- `POST /api/v1/assistant` - Interactive conversation with AI assistant
  - Request body:
    ```json
    {
      "message": "Suggest a healthy dinner",
      "user_id": "optional-user-id",
      "session_state": {}
    }
    ```
  - Returns: AI response with intent classification and results

## Docker Services

### Web (FastAPI Application)
- Port: 8000
- Hot-reload enabled in development
- Depends on: PostgreSQL, Redis

### PostgreSQL Database
- Port: 5432
- Database: ai_culinary_assistant
- Volume: postgres_data

### Redis
- Port: 6379
- Volume: redis_data

## Environment Variables

### Required Variables

#### Application
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - Secret key for security

#### AI & Nutrition Integration
- `OPENAI_API_KEY` - Your OpenAI API key
- `EDAMAM_APP_ID` - Edamam Food Database application ID
- `EDAMAM_APP_KEY` - Edamam Food Database application key

#### MCP Server Configuration
- `MCP_SERVER_CMD` - Command to run MCP server (default: `python3`)
- `MCP_SERVER_ARGS` - Path to MCP server script (default: `/app/app/core/nutrition_mcp_client.py`)
- `NUTRITION_TOOL_NAME` - Name of the nutrition tool (default: `get_nutrition_info`)

### Optional Variables

- `DEBUG` - Enable debug mode (default: False)
- `POSTGRES_USER` - PostgreSQL username
- `POSTGRES_PASSWORD` - PostgreSQL password
- `POSTGRES_DB` - PostgreSQL database name

### Docker vs Local Development

**Docker (docker-compose):**
- Use service names: `db`, `redis`
- Example: `postgresql://user:pass@db:5432/dbname`

**Local Development:**
- Use localhost: `localhost`
- Example: `postgresql://user:pass@localhost:5432/dbname`

## Development Commands

### Run Tests

#### Nutrition MCP Server Tests
```bash
# Quick test - Direct Edamam API (no Docker needed)
source .venv/bin/activate
python3 test_edamam_direct.py

# Verify Edamam credentials
python3 verify_edamam.py

# Full MCP integration test (requires Docker)
docker exec -it meal-assistant python3 test_mcp_direct.py
```

See [TEST_MCP_SERVER.md](TEST_MCP_SERVER.md) for detailed testing instructions.

#### Unit Tests
```bash
# TODO: Add test framework
pytest
```

### Run Linter
```bash
ruff check .
```

### Format Code
```bash
ruff format .
```

### Run Pre-commit on All Files
```bash
pre-commit run --all-files
```

### Docker Commands

```bash
# Build images
docker-compose build

# Rebuild and start
docker-compose up -d --build

# View logs
docker-compose logs -f [service_name]

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Execute command in container
docker-compose exec web bash
```

## Nutrition Data Integration

The application uses the Model Context Protocol (MCP) to integrate with Edamam Food Database API for nutrition information.

### How It Works

1. **MCP Server**: A standalone Python process ([app/core/nutrition_mcp_client.py](app/core/nutrition_mcp_client.py)) that communicates via stdio
2. **Data Source**: Edamam Food Database API v2 provides nutrition data per 100g
3. **Integration**: The AI agent fetches nutrition for each ingredient when generating dish information
4. **Translation**: Nutrient names are automatically translated from English to Ukrainian

### Nutrition Data Format

Each ingredient receives detailed nutrition information:

```json
{
  "uk": "Рис",
  "nutrition": [
    {"nutrition_title": "Калорії", "value": 360.0, "unit": "kcal"},
    {"nutrition_title": "Білки", "value": 6.61, "unit": "g"},
    {"nutrition_title": "Жири", "value": 0.58, "unit": "g"},
    {"nutrition_title": "Вуглеводи", "value": 79.3, "unit": "g"}
  ]
}
```

### Testing the Nutrition Integration

Run the test suite to verify the integration:

```bash
# Start Docker
docker-compose up -d

# Run integration test
docker exec -it meal-assistant python3 test_mcp_direct.py
```

For more testing options, see [TEST_MCP_SERVER.md](TEST_MCP_SERVER.md).

## Production Deployment

For production, build the Docker image without dev dependencies:

```bash
docker build -t ai-culinary-assistant:latest .
```

The production image:
- Does not include dev dependencies (pre-commit, ruff)
- Runs as non-root user
- Uses optimized Python settings

### Environment Configuration

Ensure all required environment variables are set:
- API credentials (OpenAI, Edamam)
- Database and Redis URLs
- MCP server configuration

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run pre-commit hooks: `pre-commit run --all-files`
4. Ensure all tests pass
5. Submit a pull request

## License

[Add your license here]

## Contact

[Add contact information]
