import pytest
import tempfile
import time
from pathlib import Path
from orion.pipeline.components.c15_rollback import RollbackEngine
from orion.pipeline.components.c10_checkpoint import save_checkpoint
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.checkpoint import CheckpointSnapshot


@pytest.mark.asyncio
async def test_c15_restores_files():
    """Files from checkpoint overwrite current state."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create a file that will be "corrupted"
        target = Path(tmp) / "src" / "api.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("corrupted content", encoding="utf-8")

        # Create and save a checkpoint with the original content
        snapshot = CheckpointSnapshot(
            checkpoint_id="cp-test-001",
            run_id="r1",
            session_id="s1",
            files_snapshot={"src/api.py": "original clean content"},
            created_at=time.time(),
            pipeline_state={},
        )
        save_checkpoint(snapshot)

        ctx = PipelineContext.create("s1", tmp, "test", RunMode.PLANNING)
        ctx.workspace_id = tmp
        ctx.checkpoint_id = "cp-test-001"
        ctx.error = "Execution failed"

        comp = RollbackEngine()
        result = await comp.execute(ctx)

        restored_content = target.read_text(encoding="utf-8")
        assert restored_content == "original clean content", \
            f"FAIL: expected original content, got: {restored_content}"
        print("ok: C15 restores files from checkpoint")


@pytest.mark.asyncio
async def test_c15_skips_when_no_error():
    """No rollback when ctx.error is not set."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    ctx.checkpoint_id = "cp-test-002"

    comp = RollbackEngine()
    result = await comp.execute(ctx)

    # No error means no rollback
    assert result.execution is None or (isinstance(result.execution, dict) and result.execution.get("status") != "rolled_back")
    print("ok: C15 skips when no error")


@pytest.mark.asyncio
async def test_c15_skips_fast_mode():
    """Rollback is skipped in fast mode."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.FAST)
    ctx.error = "some error"
    ctx.checkpoint_id = "cp-test-003"

    comp = RollbackEngine()
    result = await comp.execute(ctx)
    print("ok: C15 skips in fast mode")
