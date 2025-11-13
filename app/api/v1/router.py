from fastapi import APIRouter
from fastapi import HTTPException, Depends
from pydantic import ValidationError
from app.core.schemas import MealPlanRequest, MealPlanResponse, DishInfoRequest, DishInfoResponse, AssistantRequest, AssistantResponse
from app.core.auth import verify_basic_auth
from app.core.agent import build_meal_plan, dish_info
from app.core.assistant import handle_user_message

api_router = APIRouter()

@api_router.get("/ping")
async def ping():
    """Ping endpoint."""
    return {"message": "pong"}

@api_router.get("/ping2")
async def ping2():
    """Ping endpoint."""
    return {"message": "pong2"}

@api_router.get("/")
def root():
    return {"status": "ok", "/service": "meal-mind-agent"}

@api_router.post("/meal-plan", response_model=MealPlanResponse)
async def meal_plan(req: MealPlanRequest, _auth=Depends(verify_basic_auth)):
    try:
        result = await build_meal_plan(req)
        return result
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/dish-info", response_model=DishInfoResponse)
async def dish_info_endpoint(req: DishInfoRequest, _auth=Depends(verify_basic_auth)):
    try:
        result = await dish_info(req.dish_uk)
        return result
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/assistant", response_model=AssistantResponse)
async def assistant_endpoint(req: AssistantRequest, _auth=Depends(verify_basic_auth)):
    try:
        data = await handle_user_message(req.message, user_id=req.user_id, session_state=req.session_state)
        return AssistantResponse(**{
            "type": data.get("type"),
            "intent": data.get("intent"),
            "result": data.get("result"),
            "question": data.get("question"),
            "state": data.get("state") or {}
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))