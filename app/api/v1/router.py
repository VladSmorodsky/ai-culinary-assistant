from fastapi import APIRouter
from fastapi import HTTPException, Depends
from pydantic import ValidationError
from app.core.schemas import MealPlanRequest, MealPlanResponse, DishInfoRequest, DishInfoResponse, AssistantRequest, AssistantResponse
from app.core.auth import verify_basic_auth
from app.core.agent import build_meal_plan, dish_info
from app.core.assistant import handle_user_message
from app.core.log_agent import get_log_agent

log = get_log_agent()

api_router = APIRouter()

@api_router.get("/ping")
async def ping():
    """Ping endpoint."""
    log.step("ping", "start")
    log.step("ping", "success")
    return {"message": "pong"}

@api_router.get("/")
def root():
    log.step("root", "success")
    return {"status": "ok", "/service": "meal-mind-agent"}

@api_router.post("/meal-plan", response_model=MealPlanResponse)
async def meal_plan(req: MealPlanRequest, _auth=Depends(verify_basic_auth)):
    log.step("meal_plan", "start", payload=req.model_dump())
    # Explicitly log user_message for traceability
    if req.user_message:
        log.step("meal_plan", "user_message", message=req.user_message[:500])
    try:
        with log.timed("meal_plan", "build_meal_plan"):
            result = await build_meal_plan(req)
        log.step("meal_plan", "success", days=len(result.days))
        return result
    except ValidationError as ve:
        log.exception("meal_plan", "validation_error", detail=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        log.exception("meal_plan", "unexpected_error", detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/dish-info", response_model=DishInfoResponse)
async def dish_info_endpoint(req: DishInfoRequest, _auth=Depends(verify_basic_auth)):
    log.step("dish_info", "start", dish=req.dish_uk)
    try:
        with log.timed("dish_info", "fetch"):
            result = await dish_info(req.dish_uk)
        log.step("dish_info", "success", dish=result.dish_title)
        return result
    except ValidationError as ve:
        log.exception("dish_info", "validation_error", detail=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        log.exception("dish_info", "unexpected_error", detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/assistant", response_model=AssistantResponse)
async def assistant_endpoint(req: AssistantRequest, _auth=Depends(verify_basic_auth)):
    log.step("assistant", "start", user_id=req.user_id)
    try:
        with log.timed("assistant", "handle_user_message"):
            data = await handle_user_message(req.message, state=req.session_state)
        log.step("assistant", "success", intent=data.get("intent"))
        return AssistantResponse(**{
            "type": data.get("type"),
            "intent": data.get("intent"),
            "result": data.get("result"),
            "question": data.get("question"),
            "state": data.get("state") or {}
        })
    except Exception as e:
        log.exception("assistant", "unexpected_error", detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))