from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/ping")
async def ping():
    """Ping endpoint."""
    return {"message": "pong"}
