# AI Culinary Assistant

A FastAPI-based AI culinary assistant application with PostgreSQL and Redis support.

## Features

- FastAPI web framework with async support
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

## Quick Start with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-culinary-assistant
```

2. Copy the environment file and configure it:
```bash
cp .env.example .env
# Edit .env with your configuration
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

## Project Structure

```
ai-culinary-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py        # Configuration and settings
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py    # API v1 routes
│   ├── models/              # Database models
│   ├── schemas/             # Pydantic schemas
│   └── services/            # Business logic
├── .env                     # Environment variables (not in git)
├── .env.example             # Example env file for Docker
├── .env.local.example       # Example env file for local development
├── docker-compose.yml       # Docker Compose configuration
├── Dockerfile               # Docker image definition
├── pyproject.toml           # Poetry dependencies
├── poetry.lock              # Locked dependencies
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
└── README.md
```

## API Endpoints

### Root
- `GET /` - Welcome message and API information

### Health
- `GET /health` - Health check endpoint

### API v1
- `GET /api/v1/ping` - Ping endpoint

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

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - Secret key for security

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

## Production Deployment

For production, build the Docker image without dev dependencies:

```bash
docker build -t ai-culinary-assistant:latest .
```

The production image:
- Does not include dev dependencies (pre-commit, ruff)
- Runs as non-root user
- Uses optimized Python settings

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
