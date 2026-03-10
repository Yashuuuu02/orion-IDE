import pytest
from orion.pipeline.components.c10_checkpoint import CheckpointManager
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode


@pytest.mark.asyncio
async def test_c10_creates_checkpoint():
    """Checkpoint is created with file snapshot and pipeline state."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    ctx.merged = {
        "file_changes": [
            {"file_path": "src/api.py", "content": "print('hello')", "operation": "create"},
            {"file_path": "src/util.py", "content": "x = 1", "operation": "create"},
        ]
    }
    comp = CheckpointManager()
    result = await comp.execute(ctx)

    assert result.checkpoint_id is not None
    print(f"ok: checkpoint created with id {result.checkpoint_id}")


@pytest.mark.asyncio
async def test_c10_skips_fast_mode():
    """Checkpoint is not created in fast mode."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.FAST)
    comp = CheckpointManager()
    result = await comp.execute(ctx)
    assert result.checkpoint_id is None
    print("ok: checkpoint skipped in fast mode")
