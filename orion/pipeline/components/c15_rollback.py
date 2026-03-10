import logging
from pathlib import Path
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.pipeline.components.c10_checkpoint import load_checkpoint

logger = logging.getLogger(__name__)


class RollbackEngine(BaseComponent):
    component_id = "c15_rollback"
    component_name = "Rollback Engine"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            logger.info("C15: Skipping rollback in FAST mode")
            return ctx

        if not ctx.error:
            logger.info("C15: No error set, no rollback needed")
            return ctx

        if not ctx.checkpoint_id:
            logger.warning("C15: No checkpoint_id available for rollback")
            return ctx

        logger.info(f"C15: Rolling back to checkpoint {ctx.checkpoint_id}")

        # 1. Load CheckpointSnapshot
        snapshot = load_checkpoint(ctx.checkpoint_id)
        if not snapshot:
            logger.error(f"C15: Checkpoint {ctx.checkpoint_id} not found")
            return ctx

        # 2. Restore each file
        workspace_root = self._get_workspace_root(ctx)
        files_restored = 0

        for file_path, content in snapshot.files_snapshot.items():
            try:
                target = Path(workspace_root) / file_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                files_restored += 1
            except Exception as e:
                logger.error(f"C15: Failed to restore {file_path}: {e}")

        # 3. Update status
        ctx.execution = ctx.execution or {}
        if isinstance(ctx.execution, dict):
            ctx.execution["status"] = "rolled_back"

        # 4. Emit rollback.completed event
        await self._ws_emit(ctx, "rollback.completed", {
            "checkpoint_id": ctx.checkpoint_id,
            "files_restored": files_restored,
        })

        logger.info(f"C15: Rollback complete — restored {files_restored} files")
        return ctx

    def _get_workspace_root(self, ctx: PipelineContext) -> str:
        if ctx.stack_lock and ctx.stack_lock.workspace_root:
            return ctx.stack_lock.workspace_root
        return ctx.workspace_id


c15_rollback = RollbackEngine()
