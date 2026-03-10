import pytest
from unittest.mock import patch, MagicMock
from orion.pipeline.components.c09_validation import ValidationGate, FAST_LAYERS, PLANNING_LAYERS
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.validation import ValidationLayer


@pytest.mark.asyncio
async def test_c09_fast_mode_only_syntax_and_type():
    """In fast mode, only SYNTAX and TYPE layers run."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.FAST)
    comp = ValidationGate()

    result = await comp.execute(ctx)

    assert result.validation is not None
    layer_names = [lr.layer for lr in result.validation.layers]
    assert ValidationLayer.SYNTAX in layer_names
    assert ValidationLayer.TYPE in layer_names
    assert ValidationLayer.SECURITY not in layer_names
    assert ValidationLayer.FORMAL not in layer_names
    assert len(result.validation.layers) == 2
    print("ok: fast mode runs only SYNTAX and TYPE layers")


@pytest.mark.asyncio
async def test_c09_planning_mode_all_layers():
    """In planning mode, all 6 layers run."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    comp = ValidationGate()

    result = await comp.execute(ctx)

    assert result.validation is not None
    assert len(result.validation.layers) == 6
    layer_names = {lr.layer for lr in result.validation.layers}
    assert layer_names == {
        ValidationLayer.SYNTAX, ValidationLayer.TYPE, ValidationLayer.SECURITY,
        ValidationLayer.PERFORMANCE, ValidationLayer.INTEGRATION, ValidationLayer.FORMAL,
    }
    print("ok: planning mode runs all 6 layers")


@pytest.mark.asyncio
async def test_c09_missing_tool_skipped():
    """Missing tsc/mypy produces skipped result, not failure."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.FAST)
    # Set stack to typescript to trigger tsc check
    from orion.schemas.stack import StackLock
    import time
    ctx.stack_lock = StackLock(
        lock_hash="h", language="typescript", framework="react",
        test_runner="jest", package_manager="npm", dependencies={},
        workspace_root="/tmp", locked_at=time.time(),
    )

    comp = ValidationGate()

    # Mock shutil.which to return None (tool not found)
    with patch('orion.pipeline.components.c09_validation.shutil.which', return_value=None):
        result = await comp.execute(ctx)

    assert result.validation is not None
    type_layer = [r for r in result.validation.layers if r.layer == ValidationLayer.TYPE][0]
    assert type_layer.passed is True
    assert any("tool not found" in issue for issue in type_layer.issues)
    print("ok: missing tool produces skipped result, not failure")
