import asyncio
import asyncio.subprocess
import json
import logging
from typing import Any
from pathlib import Path
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from sqlalchemy import text
from datetime import datetime, timezone, timedelta
from orion.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class AtomicExecutor(BaseComponent):
    component_id = "c11_executor"
    component_name = "Atomic Executor"

    def __init__(self):
        super().__init__()

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        workspace_root = self._get_workspace_root(ctx)
        if not workspace_root:
            ctx.error = "No workspace_root available for file writes"
            return ctx

        file_changes = self._get_file_changes(ctx)
        if not file_changes:
            logger.error("C11: AI generated no code (file_changes is empty)")
            ctx.error = "AI generated no code"
            return ctx

        if ctx.mode == RunMode.FAST:
            await self._create_fast_snapshot(ctx, workspace_root)

        files_written = 0
        total = len(file_changes)

        # Emit start event so UI can show progress bar
        await self._ws_emit(ctx, "execution.started", {
            "total_files": total,
            "workspace_root": workspace_root
        })

        try:
            for i, fc in enumerate(file_changes):
                if ctx.cancelled:
                    break

                file_path = fc.get("file_path", "") if isinstance(fc, dict) else getattr(fc, "file_path", "")
                operation = fc.get("operation", "create") if isinstance(fc, dict) else getattr(fc, "operation", "create")
                content = fc.get("content", "") if isinstance(fc, dict) else getattr(fc, "content", "")

                target = Path(workspace_root) / file_path
                lines_before = 0
                lines_after = 0

                try:
                    if operation == "create":
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content or "", encoding="utf-8")
                        lines_after = len((content or "").splitlines())
                        files_written += 1

                        await self._ws_emit(ctx, "file.created", {
                            "file_path": file_path,
                            "lines_added": lines_after,
                            "lines_removed": 0,
                            "index": i + 1,
                            "total": total,
                            "absolute_path": str(target),
                            "content": content or "",
                        })

                    elif operation == "modify":
                        # Count lines before
                        if target.exists():
                            lines_before = len(target.read_text(encoding="utf-8").splitlines())
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content or "", encoding="utf-8")
                        lines_after = len((content or "").splitlines())
                        files_written += 1

                        await self._ws_emit(ctx, "file.modified", {
                            "file_path": file_path,
                            "lines_added": max(0, lines_after - lines_before),
                            "lines_removed": max(0, lines_before - lines_after),
                            "lines_before": lines_before,
                            "lines_after": lines_after,
                            "index": i + 1,
                            "total": total,
                            "absolute_path": str(target),
                            "content": content or "",
                        })

                    elif operation == "delete":
                        if target.exists():
                            lines_before = len(target.read_text(encoding="utf-8").splitlines())
                            target.unlink()
                        files_written += 1

                        await self._ws_emit(ctx, "file.deleted", {
                            "file_path": file_path,
                            "lines_removed": lines_before,
                            "lines_added": 0,
                            "index": i + 1,
                            "total": total,
                            "absolute_path": str(target),
                        })

                    elif operation == "mkdir":
                        target.mkdir(parents=True, exist_ok=True)
                        files_written += 1

                        await self._ws_emit(ctx, "folder.created", {
                            "file_path": file_path,
                            "index": i + 1,
                            "total": total,
                            "absolute_path": str(target),
                        })

                except Exception as file_err:
                    logger.error(f"C11: Failed on {file_path}: {file_err}")
                    await self._ws_emit(ctx, "file.error", {
                        "file_path": file_path,
                        "error": str(file_err),
                        "index": i + 1,
                        "total": total,
                    })

            ctx.execution = {
                "files_written": files_written,
                "total": total,
                "status": "completed"
            }

            if files_written == 0:
                ctx.error = "AI generated no code"
                logger.error(f"C11: Failed to write any files (total={total}). Pipeline failed.")
            else:
                await self._ws_emit(ctx, "execution.complete", {
                    "files_written": files_written,
                    "total": total,
                })
                logger.info(f"C11: Applied {files_written}/{total} file changes")

        except Exception as e:
            logger.error(f"C11: Execution failed: {e}")
            ctx.error = f"Atomic execution failed: {e}"

        return ctx

    def _get_workspace_root(self, ctx: PipelineContext) -> str | None:
        if ctx.stack_lock and hasattr(ctx.stack_lock, 'workspace_root') and ctx.stack_lock.workspace_root:
            return ctx.stack_lock.workspace_root
        if ctx.workspace_id and ctx.workspace_id != "default":
            return ctx.workspace_id
        return None

    def _get_file_changes(self, ctx: PipelineContext) -> list:
        if ctx.merged and isinstance(ctx.merged, dict):
            changes = ctx.merged.get("file_changes", [])
            if changes:
                return changes
        if ctx.agent_outputs:
            changes = []
            for output in ctx.agent_outputs:
                if hasattr(output, 'file_changes'):
                    for fc in getattr(output, 'file_changes', []):
                        changes.append(fc)
            if changes:
                return changes
        # Fallback: check task_dag for file plan
        if ctx.task_dag and isinstance(ctx.task_dag, dict):
            return ctx.task_dag.get("file_changes", [])
        return []



    async def _create_fast_snapshot(self, ctx: PipelineContext, workspace_root: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD",
                cwd=workspace_root,
                stdout=asyncio.subprocess.PIPE,  # type: ignore[attr-defined]
                stderr=asyncio.subprocess.PIPE,  # type: ignore[attr-defined]
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            diff_output: str = (stdout or b"").decode("utf-8", errors="replace")
            
            expires = datetime.now(timezone.utc) + timedelta(hours=2)
            async with AsyncSessionLocal() as db:
                await db.execute(text(
                    "UPDATE pipeline_runs SET fast_result=:res, fast_result_expires_at=:exp WHERE run_id=:rid"
                ), {'res': diff_output, 'exp': expires, 'rid': ctx.run_id})
                await db.commit()
            
            logger.info(f"C11: Fast snapshot stored in DB for run: {ctx.run_id}")
        except Exception as e:
            logger.warning(f"C11: Failed to create fast snapshot: {e}")


c11_executor = AtomicExecutor()
