import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

# IMPORTANT: Mock Redis before importing components
import orion.core.redis_client
class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, k): return self.data.get(k)
    async def setex(self, k, t, v): self.data[k] = v
    async def set(self, k, v, ex=None): self.data[k] = v
    async def rpush(self, k, v): pass
    async def lrange(self, k, s, e): return []
    async def ltrim(self, k, s, e): pass
    async def expire(self, k, t): pass
    async def delete(self, k): self.data.pop(k, None)
    async def keys(self, pattern): return [k for k in self.data.keys() if k.startswith(pattern.replace('*', ''))]

orion.core.redis_client.get_redis = lambda: MockRedis()

from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.settings import RunConfig, AgentRunConfig
from orion.schemas.agent import AgentRole
from orion.pipeline.runner import PipelineRunner
from orion.pipeline.runner import pipeline_runner

@pytest.mark.asyncio
async def test_pipeline_planning_full_run():
    # 1. Create PipelineContext with RunMode.PLANNING
    os.environ["MOCK_LLM"] = "true"
    run_config = RunConfig(
        agent_configs=[AgentRunConfig(role=AgentRole.BACKEND, enabled=True, token_limit=50000)]
    )
    ctx = PipelineContext.create("s1", "w1", "add login endpoint", RunMode.PLANNING, run_config=run_config)
    ctx.active_provider = "openai"

    # Mock ws_emit
    emitted = []
    async def mock_ws_emit(ctx, event, payload=None):
        emitted.append(event)

    # We need to auto-resolve approvals (IISG from C03, Planner from C05)
    async def mock_wait_for_approval(run_id, approval_type, timeout_seconds=300):
        return {"approved": True, "decision": "approve"}

    original_wait = pipeline_runner._wait_for_approval
    original_check = pipeline_runner._check_cost_gate
    pipeline_runner._wait_for_approval = mock_wait_for_approval
    pipeline_runner._check_cost_gate = AsyncMock()

    try:
        with patch("orion.pipeline.base_component.BaseComponent._ws_emit", new_callable=AsyncMock):
            # 2. Run full pipeline via PipelineRunner
            ctx = await pipeline_runner.run(ctx, mock_ws_emit)
    finally:
        pipeline_runner._wait_for_approval = original_wait
        pipeline_runner._check_cost_gate = original_check

    # 3. Asserts ctx.intent is populated (C01 ran)
    assert ctx.intent is not None, "FAIL: ctx.intent is None (C01 did not run)"
    assert ctx.intent.intent_type is not None

    # 4. Asserts ctx.stack_lock is populated (C02 ran)
    assert ctx.stack_lock is not None, "FAIL: ctx.stack_lock is None (C02 did not run)"
    assert ctx.stack_lock.language is not None

    # 5. Asserts ctx.iisg is populated (C03 ran)
    assert ctx.iisg is not None, "FAIL: ctx.iisg is None (C03 did not run)"
    assert len(ctx.iisg.clauses) > 0

    # 6. Asserts ctx.validation is populated (C09 ran)
    assert ctx.validation is not None, "FAIL: ctx.validation is None (C09 did not run)"
    assert len(ctx.validation.layers) > 0

    # 7. Asserts ctx.error is None
    assert ctx.error is None, f"FAIL: Pipeline failed with error: {ctx.error}"

    # 8. Asserts pipeline.completed WS event was emitted
    assert "pipeline.started" in emitted, "FAIL: pipeline.started not emitted"
    assert "pipeline.completed" in emitted, "FAIL: pipeline.completed not emitted"

    print("ok: full pipeline run completed successfully")

@pytest.mark.asyncio
async def test_determinism():
    os.environ["MOCK_LLM"] = "true"

    # Run same prompt 3 times with same session_id and workspace
    ctx1 = PipelineContext.create("sess_1", "ws_1", "exact same prompt", RunMode.PLANNING)
    ctx2 = PipelineContext.create("sess_1", "ws_1", "exact same prompt", RunMode.PLANNING)
    ctx3 = PipelineContext.create("sess_1", "ws_1", "exact same prompt", RunMode.PLANNING)

    # Run IDs must be identical
    assert ctx1.run_id == ctx2.run_id == ctx3.run_id

    # Int versions must be identical
    assert ctx1.run_id_int == ctx2.run_id_int == ctx3.run_id_int

@pytest.mark.asyncio
async def test_different_prompts_produce_different_run_ids():
    ctx1 = PipelineContext.create("sess_1", "ws_1", "prompt A", RunMode.PLANNING)
    ctx2 = PipelineContext.create("sess_1", "ws_1", "prompt B", RunMode.PLANNING)

    assert ctx1.run_id != ctx2.run_id
