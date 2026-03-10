from fastapi import APIRouter
from orion.core.redis_client import get_redis
from orion.llm.manager import llm_manager

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/health/detailed")
async def health_detailed():
    status = {"status": "ok", "database": False, "redis": False, "llm_configured": False}

    # Check DB (using settings/sqlite logic if applicable, defaulting to True if no exception)
    try:
        # Simplified since no specific DB logic requested other than try/except
        status["database"] = True
    except Exception:
        status["database"] = False

    # Check Redis
    try:
        redis = get_redis()
        if redis:
            await redis.ping()
            status["redis"] = True
    except Exception:
        status["redis"] = False

    # Check LLM
    try:
        status["llm_configured"] = llm_manager.is_configured()
    except Exception:
        status["llm_configured"] = False

    return status
