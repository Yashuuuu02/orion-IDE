import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock
from orion.pipeline.components.c11_executor import AtomicExecutor
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.stack import StackLock


class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, k): return self.data.get(k)
    async def setex(self, k, t, v): self.data[k] = v


@pytest.mark.asyncio
async def test_c11_write_creates_file():
    """Actual file is written to temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        ctx = PipelineContext.create("s1", tmp, "test", RunMode.PLANNING)
        ctx.stack_lock = StackLock(
            lock_hash="h", language="python", framework="none",
            test_runner="pytest", package_manager="pip", dependencies={},
            workspace_root=tmp, locked_at=time.time(),
        )
        ctx.merged = {
            "file_changes": [
                {"file_path": "src/hello.py", "operation": "create", "content": "print('hello')"},
            ]
        }

        comp = AtomicExecutor()
        result = await comp.execute(ctx)

        target = Path(tmp) / "src" / "hello.py"
        assert target.exists(), f"FAIL: file not created at {target}"
        assert target.read_text(encoding="utf-8") == "print('hello')"
        assert result.execution["files_written"] == 1
        print("ok: C11 write creates actual file")


@pytest.mark.asyncio
async def test_c11_fast_mode_snapshot():
    """Redis key exists after Fast Mode execution."""
    mock_redis = MockRedis()

    with tempfile.TemporaryDirectory() as tmp:
        ctx = PipelineContext.create("s1", tmp, "test", RunMode.FAST)
        ctx.stack_lock = StackLock(
            lock_hash="h", language="python", framework="none",
            test_runner="pytest", package_manager="pip", dependencies={},
            workspace_root=tmp, locked_at=time.time(),
        )
        ctx.merged = {
            "file_changes": [
                {"file_path": "fast.py", "operation": "create", "content": "x = 1"},
            ]
        }

        comp = AtomicExecutor()

        with patch('orion.pipeline.components.c11_executor.get_redis', return_value=mock_redis):
            result = await comp.execute(ctx)

        cache_key = f"fast_snapshot:{ctx.run_id}"
        assert cache_key in mock_redis.data, f"FAIL: Redis key {cache_key} not found"
        print("ok: C11 fast mode snapshot stored in Redis")


@pytest.mark.asyncio
async def test_c11_delete_file():
    """Delete operation removes a file."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "to_delete.py"
        target.write_text("old content", encoding="utf-8")

        ctx = PipelineContext.create("s1", tmp, "test", RunMode.PLANNING)
        ctx.workspace_id = tmp
        ctx.merged = {
            "file_changes": [
                {"file_path": "to_delete.py", "operation": "delete", "content": ""},
            ]
        }

        comp = AtomicExecutor()
        result = await comp.execute(ctx)

        assert not target.exists(), "FAIL: file not deleted"
        print("ok: C11 delete removes file")
