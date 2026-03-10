from fastapi import APIRouter

from orion.api.health import router as health_router
from orion.api.pipeline import router as pipeline_router
from orion.api.settings import router as settings_router
from orion.api.memory import router as memory_router
from orion.api.search import router as search_router

api_router = APIRouter()

# Health doesn't go under /api/v1 prefix based on requirements
# It will be included directly in main.py

# Mount others under v1
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(pipeline_router)
api_v1_router.include_router(settings_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(search_router)

# Note: The problem description asks to import and mount: health, pipeline, settings, memory routers
# "All API routes under /api/v1/ prefix except health"
