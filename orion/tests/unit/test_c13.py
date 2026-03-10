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
