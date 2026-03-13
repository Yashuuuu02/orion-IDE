import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from orion.schemas.pipeline import RunMode
from orion.schemas.settings import RunConfig

router = APIRouter()

class PipelineRunRequest(BaseModel):
    prompt: str
    session_id: str
    workspace_id: str = "default"
    mode: str = "fast"

@router.post("/pipeline/run")
async def run_pipeline(req: PipelineRunRequest):
    from orion.pipeline.context import PipelineContext
    from orion.pipeline.runner import PipelineRunner
    from orion.api.ws import ws_manager

    try:
        run_mode = RunMode(req.mode)
    except ValueError:
        run_mode = RunMode.FAST

    ctx = PipelineContext.create(
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        raw_prompt=req.prompt,
        mode=run_mode,
        run_config=RunConfig()
    )

    async def ws_emit(ctx, event_type: str, payload: dict):
        await ws_manager.emit(req.session_id, {
            "type": event_type,
            "run_id": ctx.run_id,
            **payload
        })

    runner = PipelineRunner()
    asyncio.create_task(runner.run(ctx, ws_emit))

    return {
        "run_id": ctx.run_id,
        "session_id": req.session_id,
        "mode": run_mode.value,
        "status": "started"
    }

class RollbackRequest(BaseModel):
    checkpoint_id: str
    run_id: str

@router.post("/pipeline/rollback")
async def rollback_pipeline(req: RollbackRequest):
    return {"status": "rolled_back", "checkpoint_id": req.checkpoint_id}

@router.get("/pipeline/status/{run_id}")
async def pipeline_status(run_id: str):
    try:
        from orion.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT status FROM pipeline_runs WHERE run_id=:rid"), {'rid': run_id})
            row = result.fetchone()
            if row:
                return {"status": row[0]}
    except Exception:
        pass

    return {"status": "not_found"}


class ApprovalRequest(BaseModel):
    decision: dict
    approval_type: str = "planner"

@router.post("/pipeline/approve/{run_id}")
async def approve_pipeline(run_id: str, req: ApprovalRequest):
    from orion.api.ws import ws_manager
    from orion.pipeline.runner import pipeline_runner
    await pipeline_runner.resolve_approval(run_id, req.decision)
    return {"status": "approved", "run_id": run_id, "decision": req.decision}
