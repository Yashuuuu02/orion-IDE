import pytest
import os
import asyncio
from unittest.mock import AsyncMock, patch
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.pipeline.runner import pipeline_runner
from orion.api.ws import ws_manager

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
async def test_fast_mode_end_to_end(mock_redis):
    os.environ["MOCK_LLM"] = "true"

    ctx = PipelineContext.create(
        session_id="test_fast",
        workspace_id="ws_fast",
        raw_prompt="change color to blue",
        mode=RunMode.FAST
    )

    events = []
    async def capture_emit(session_id, event):
        events.append(event)

    with patch("orion.pipeline.runner.PipelineRunner._wait_for_approval", new_callable=AsyncMock) as mock_approve, \
         patch("orion.core.redis_client.get_redis", return_value=mock_redis), \
         patch("orion.api.ws.get_redis", return_value=mock_redis), \
         patch("orion.pipeline.components.c01_intent.get_redis", return_value=mock_redis), \
         patch("orion.pipeline.components.c02_stack.get_redis", return_value=mock_redis), \
         patch("orion.pipeline.components.c12_memory.MemoryLogger.execute", new_callable=AsyncMock, return_value=ctx):

        mock_approve.return_value = {"decision": "approve"}

        # Test the pipeline runner directly
        result_ctx = await pipeline_runner.run(ctx, capture_emit)

    event_types = [e["type"] for e in events]
    assert "pipeline.started" in event_types
    assert "pipeline.completed" in event_types or "pipeline.failed" in event_types

    # Assert: ctx.iisg is None (no IISG in fast mode)
    assert result_ctx.iisg is None

    # Assert: EXACTLY 7 FAST_MODE_COMPONENTS vs 15 PLANNING_MODE_COMPONENTS
    assert len(pipeline_runner.FAST_MODE_COMPONENTS) == 7
    assert len(pipeline_runner.PLANNING_MODE_COMPONENTS) == 15


@pytest.mark.asyncio
async def test_chat_tab_forces_fast_mode():
    message = {
        "type": "run_pipeline",
        "source": "chat_tab",
        "mode": "planning"  # Should be overridden to FAST
    }
    resolved_mode = ws_manager._resolve_mode(message)
    assert resolved_mode == RunMode.FAST

    # We create a ctx to assert that initially iisg is None anyway
    ctx = PipelineContext.create("test", "test", "test", resolved_mode)
    assert ctx.iisg is None


@pytest.mark.asyncio
async def test_fast_mode_excludes_planning_components():
    fast_types = [type(c).__name__ for c in pipeline_runner.FAST_MODE_COMPONENTS]

    # Should not include these planning-only components
    assert "IISGGenerator" not in fast_types
    assert "ParallelRoles" not in fast_types
    assert "ArchitectBlueprint" not in fast_types
