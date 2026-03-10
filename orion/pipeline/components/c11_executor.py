import asyncio
import json
import logging
from pathlib import Path
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class AtomicExecutor(BaseComponent):
    component_id = "c11_executor"
    component_name = "Atomic Executor"

    def __init__(self):
        super().__init__()
        self._redis = None  # Can be injected for testing

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        # Get workspace root
        workspace_root = self._get_workspace_root(ctx)
        if not workspace_root:
            ctx.error = "No workspace_root available for file writes"
            return ctx

        # Get file changes
        file_changes = self._get_file_changes(ctx)
        if not file_changes:
            logger.info("C11: No file changes to apply")
            return ctx

        # Fast Mode: create git diff snapshot before writing
        if ctx.mode == RunMode.FAST:
            await self._create_fast_snapshot(ctx, workspace_root)

        # Apply file changes
        files_written = 0
        try:
            for fc in file_changes:
                file_path = fc.get("file_path", "") if isinstance(fc, dict) else getattr(fc, "file_path", "")
                operation = fc.get("operation", "") if isinstance(fc, dict) else getattr(fc, "operation", "")
                content = fc.get("content", "") if isinstance(fc, dict) else getattr(fc, "content", "")

                target = Path(workspace_root) / file_path

                if operation == "create":
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content or "", encoding="utf-8")
                    files_written += 1
                elif operation == "modify":
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content or "", encoding="utf-8")
                    files_written += 1
                elif operation == "delete":
                    if target.exists():
                        target.unlink()
                    files_written += 1

            ctx.execution = {"files_written": files_written, "status": "completed"}
            await self._ws_emit(ctx, "execution.complete", {
                "files_written": files_written,
            })
            logger.info(f"C11: Applied {files_written} file changes")

        except Exception as e:
            logger.error(f"C11: File write failed: {e}")
            ctx.error = f"Atomic execution failed: {e}"
            if ctx.mode == RunMode.PLANNING and ctx.checkpoint_id:
                ctx.error = f"Execution failed, rollback needed: {e}"

        return ctx

    def _get_workspace_root(self, ctx: PipelineContext) -> str | None:
        if ctx.stack_lock and ctx.stack_lock.workspace_root:
            return ctx.stack_lock.workspace_root
        if ctx.workspace_id:
            return ctx.workspace_id
        return None

    def _get_file_changes(self, ctx: PipelineContext) -> list:
        if ctx.merged and isinstance(ctx.merged, dict):
            return ctx.merged.get("file_changes", [])
        if ctx.agent_outputs:
            changes = []
            for output in ctx.agent_outputs:
                for fc in output.file_changes:
                    changes.append(fc)
            return changes
        return []

    def _get_redis(self):
        """Use injected _redis if available, otherwise get_redis()."""
        if self._redis is not None:
            return self._redis
        return get_redis()

    async def _create_fast_snapshot(self, ctx: PipelineContext, workspace_root: str):
        """Create git diff snapshot and store in Redis."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD",
                cwd=workspace_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            diff_output = (stdout or b"").decode("utf-8", errors="replace")

            redis = self._get_redis()
            cache_key = f"fast_snapshot:{ctx.run_id}"
            if hasattr(redis, 'set'):
                await redis.set(cache_key, diff_output, ex=7200)
            else:
                await redis.setex(cache_key, 7200, diff_output)
            logger.info(f"C11: Fast snapshot stored in Redis: {cache_key}")
        except Exception as e:
            logger.warning(f"C11: Failed to create fast snapshot: {e}")


c11_executor = AtomicExecutor()
