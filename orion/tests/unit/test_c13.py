import pytest
import pytest_asyncio
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.pipeline.components.c13_patterns import c13_patterns

@pytest.fixture
def ctx():
    return PipelineContext.create("test_session", "w1", "test prompt", RunMode.PLANNING)

@pytest.mark.asyncio
async def test_c13_runs_as_background(ctx):
    # Setup some dummy data
    ctx.agent_outputs = [{"id": "1", "data": "test"}]
    ctx.validation = type("val", (), {"is_valid": True})()

    result = await c13_patterns.execute(ctx)

    # Assert ctx returned unchanged
    assert result is ctx
    # Assert no error set
    assert result.error is None

@pytest.mark.asyncio
async def test_c13_handles_empty_outputs(ctx):
    # Empty state
    ctx.agent_outputs = []
    ctx.validation = None

    # Should not crash
    result = await c13_patterns.execute(ctx)

    assert result is ctx
    assert result.error is None

@pytest.mark.asyncio
async def test_c13_extracts_agent_success_pattern(ctx):
    from orion.schemas.agent import AgentOutput

    # Setup one successful AgentOutput
    ctx.agent_outputs = [
        AgentOutput(
            run_id="test_run",
            agent_role="backend",
            success=True,
            tokens_used=150,
            duration_ms=400,
            iisg_satisfied=[],
            file_changes=[{"file_path": "test.py", "operation": "add", "reason": "testing"}]
        )
    ]

    patterns = c13_patterns._extract_patterns(ctx)
    assert len(patterns) == 1
    assert patterns[0]["type"] == "agent_success"
    assert patterns[0]["data"]["agent_role"] == "backend"
    assert patterns[0]["data"]["files_changed"] == 1
    assert patterns[0]["data"]["tokens_used"] == 150

@pytest.mark.asyncio
async def test_c13_store_failure_is_nonfatal(ctx):
    from unittest.mock import patch, AsyncMock

    ctx.agent_outputs = []

    # Mock to raise an exception
    with patch("orion.pipeline.components.c13_patterns.C13PatternRecognition._store_patterns", side_effect=Exception("DB connection failed")):
        result = await c13_patterns.execute(ctx)

    # Assert ctx is unchanged and error is None
    assert result.error is None
    assert result is ctx
