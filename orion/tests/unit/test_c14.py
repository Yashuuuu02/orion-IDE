import pytest
from unittest.mock import patch, AsyncMock
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.pipeline.components.c14_failure import c14_failure

@pytest.fixture
def ctx():
    return PipelineContext.create("test_session", "w1", "test prompt", RunMode.PLANNING)

@pytest.mark.asyncio
async def test_c14_skips_when_no_error(ctx):
    ctx.error = None
    original_strategy = getattr(ctx, "recovery_strategy", None)

    result = await c14_failure.execute(ctx)

    assert result is ctx
    # Assert strategy not set
    assert getattr(result, "recovery_strategy", None) == original_strategy

@pytest.mark.asyncio
async def test_c14_sets_recovery_strategy(ctx):
    ctx.error = "Test failure in execution"
    # Ensure it's not set
    if hasattr(ctx, "recovery_strategy"):
        delattr(ctx, "recovery_strategy")

    with patch("orion.pipeline.components.c14_failure.llm_manager.get_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "partial_rollback"

        result = await c14_failure.execute(ctx)

        assert result is ctx
        assert hasattr(result, "recovery_strategy")
        assert result.recovery_strategy == "partial_rollback"
        assert result.recovery_strategy in ["retry", "rollback", "partial_rollback", "user_input_required"]
