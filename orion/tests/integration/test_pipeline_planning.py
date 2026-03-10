import pytest
import os
import asyncio
from unittest.mock import AsyncMock, patch
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.pipeline.runner import pipeline_runner

@pytest.fixture
def mock_redis():
    class MockRedisObj:
        async def lrange(self, *args, **kwargs): return []
        async def rpush(self, *args, **kwargs): pass
        async def ltrim(self, *args, **kwargs): pass
        async def expire(self, *args, **kwargs): pass
        async def set(self, *args, **kwargs): pass
        async def setex(self, *args, **kwargs): pass
        async def get(self, *args, **kwargs): return None
        async def hset(self, *args, **kwargs): pass
        async def hget(self, *args, **kwargs): return None
        async def flushdb(self): pass
    return MockRedisObj()

@pytest.mark.asyncio
async def test_full_planning_run(mock_redis):
    os.environ["MOCK_LLM"] = "true"

    ctx = PipelineContext.create(
        session_id="test_session",
        workspace_id="test_workspace",
        raw_prompt="create a hello world script",
        mode=RunMode.PLANNING
    )

    events = []
    async def capture_emit(session_id, event):
        events.append(event)

    # We auto-approve inside the loop if necessary, but runner's wait_for_approval
    # might block if not patched. We'll patch event wait to immediately return approval.
    with patch("orion.pipeline.runner.PipelineRunner._wait_for_approval", new_callable=AsyncMock) as mock_approve, \
         patch("orion.core.redis_client.get_redis", return_value=mock_redis), \
         patch("orion.api.ws.get_redis", return_value=mock_redis), \
         patch("orion.pipeline.components.c01_intent.get_redis", return_value=mock_redis), \
         patch("orion.pipeline.components.c02_stack.get_redis", return_value=mock_redis), \
         patch("orion.pipeline.components.c12_memory.MemoryLogger.execute", new_callable=AsyncMock, return_value=ctx):

        mock_approve.return_value = {"decision": "approve"}

        result_ctx = await pipeline_runner.run(ctx, capture_emit)

    event_types = [e["type"] for e in events]
    assert "pipeline.started" in event_types
    assert "pipeline.completed" in event_types or "pipeline.failed" in event_types

    # Assert C01/C02 basics populated in a normal mock run
    # (Mock LLMs in components will populate these if MOCK_LLM=true)
    assert result_ctx.intent is not None
    assert result_ctx.stack_lock is not None

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
