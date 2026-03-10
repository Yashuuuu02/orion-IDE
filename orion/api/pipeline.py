from fastapi import APIRouter
from pydantic import BaseModel
from orion.core.redis_client import get_redis

router = APIRouter()

class RollbackRequest(BaseModel):
    checkpoint_id: str
    run_id: str

@router.post("/pipeline/rollback")
async def rollback_pipeline(req: RollbackRequest):
    return {"status": "rolled_back", "checkpoint_id": req.checkpoint_id}

@router.get("/pipeline/status/{run_id}")
async def pipeline_status(run_id: str):
    try:
        redis = get_redis()
        # Stub logic matching requirements
        status_data = await redis.hget(f"pipeline:{run_id}", "status")
        if status_data:
            return {"status": status_data}
    except Exception:
        pass

    return {"status": "not_found"}
