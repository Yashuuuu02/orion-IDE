import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.pipeline.runner import pipeline_runner

@pytest.mark.asyncio
async def test_determinism_planning_mode():
    """
    Runs the same prompt 10 times.
    All 10 run_ids must be IDENTICAL.
    This is the proof of Orion's core determinism promise.
    """
    session_id = "det-test-session"
    workspace_id = "det-test-workspace"
    raw_prompt = "add a login endpoint to the Express API"

    run_ids = []
    run_id_ints = []
    contract_hashes = []

    async def mock_emit(session_id, event):
        pass

    with patch("orion.pipeline.runner.PipelineRunner._wait_for_approval", new_callable=AsyncMock) as mock_approve:
        mock_approve.return_value = {"decision": "approve"}

        for _ in range(10):
            ctx = PipelineContext.create(
                session_id=session_id,
                workspace_id=workspace_id,
                raw_prompt=raw_prompt,
                mode=RunMode.PLANNING
            )

            ctx = await pipeline_runner.run(ctx, mock_emit)

            run_ids.append(ctx.run_id)
            run_id_ints.append(ctx.run_id_int)
            if ctx.iisg:
                contract_hashes.append(ctx.iisg.contract_hash)

    # Core assertions
    assert len(set(run_ids)) == 1, f"DETERMINISM BROKEN: got {len(set(run_ids))} different run_ids"
    assert len(set(run_id_ints)) == 1
    if contract_hashes:
        assert len(set(contract_hashes)) == 1

@pytest.mark.asyncio
async def test_different_prompts_produce_different_run_ids():
    ctx1 = PipelineContext.create("s1", "w1", "add login endpoint", RunMode.PLANNING)
    ctx2 = PipelineContext.create("s1", "w1", "remove the login endpoint", RunMode.PLANNING)
    assert ctx1.run_id != ctx2.run_id

@pytest.mark.asyncio
async def test_same_inputs_always_same_run_id():
    """Unit test — no pipeline needed, just context creation."""
    ctx_a = PipelineContext.create("sess", "ws", "fix the bug", RunMode.PLANNING)
    ctx_b = PipelineContext.create("sess", "ws", "fix the bug", RunMode.PLANNING)
    assert ctx_a.run_id == ctx_b.run_id
    assert ctx_a.run_id_int == ctx_b.run_id_int
