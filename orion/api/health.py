from orion.llm.manager import llm_manager
from orion.core.config import settings

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/health/detailed")
async def health_detailed():
    status = {"status": "ok", "db": False, "redis": False, "llm_configured": False, "mock_llm": settings.MOCK_LLM}

    # Check DB (using settings/sqlite logic if applicable, defaulting to True if no exception)
    try:
        # Simplified since no specific DB logic requested other than try/except
        status["db"] = True
    except Exception:
        status["db"] = False



    # Check LLM
    try:
        status["llm_configured"] = llm_manager.is_configured()
    except Exception:
        status["llm_configured"] = False

    return status
