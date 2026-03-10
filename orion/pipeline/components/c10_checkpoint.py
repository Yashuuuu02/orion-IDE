import json
import logging
import time
import uuid
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.checkpoint import CheckpointSnapshot
from orion.core.metrics import checkpoint_size_bytes

logger = logging.getLogger(__name__)


class CheckpointManager(BaseComponent):
    component_id = "c10_checkpoint"
    component_name = "Checkpoint Manager"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            logger.info("C10: Skipping checkpoint in FAST mode")
            return ctx

        logger.info("C10: Creating checkpoint")

        # 1. Serialize file snapshot from ctx.merged
        files_snapshot: dict[str, str] = {}
        if ctx.merged and isinstance(ctx.merged, dict):
            file_changes = ctx.merged.get("file_changes", [])
            for fc in file_changes:
                if isinstance(fc, dict):
                    path = fc.get("file_path", "")
                    content = fc.get("content", "")
                    if path:
                        files_snapshot[path] = content or ""

        # 2. Serialize pipeline_state
        pipeline_state = {
            "intent": ctx.intent.model_dump() if ctx.intent else None,
            "iisg": ctx.iisg.model_dump() if ctx.iisg else None,
            "blueprint": ctx.blueprint,
            "task_dag": ctx.task_dag,
            "validation": ctx.validation.model_dump() if ctx.validation else None,
        }

        # 3. Create CheckpointSnapshot
        checkpoint_id = str(uuid.uuid4())
        snapshot = CheckpointSnapshot(
            checkpoint_id=checkpoint_id,
            run_id=ctx.run_id,
            session_id=ctx.session_id,
            files_snapshot=files_snapshot,
            created_at=time.time(),
            pipeline_state=pipeline_state,
        )

        # 4. Save to PostgreSQL (mock-safe: store on ctx for now)
        ctx.checkpoint_id = checkpoint_id
        checkpoint_size_bytes.set(len(json.dumps(files_snapshot)))

        # Store snapshot in a retrievable location for C15
        if not hasattr(ctx, '_checkpoint_snapshots'):
            ctx._checkpoint_snapshots = {}
        ctx._checkpoint_snapshots = {checkpoint_id: snapshot}

        # 5. Emit checkpoint event
        await self._ws_emit(ctx, "checkpoint.created", {
            "checkpoint_id": checkpoint_id,
            "file_count": len(files_snapshot),
        })

        logger.info(f"C10: Checkpoint {checkpoint_id} created with {len(files_snapshot)} files")
        return ctx


# Module-level checkpoint store for cross-component access
_checkpoint_store: dict[str, CheckpointSnapshot] = {}


def save_checkpoint(snapshot: CheckpointSnapshot):
    _checkpoint_store[snapshot.checkpoint_id] = snapshot


def load_checkpoint(checkpoint_id: str) -> CheckpointSnapshot | None:
    return _checkpoint_store.get(checkpoint_id)


c10_checkpoint = CheckpointManager()
