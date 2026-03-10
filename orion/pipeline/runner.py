import asyncio
import os
import logging
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.core.config import settings
from orion.pipeline.components.c01_intent import c01_intent
from orion.pipeline.components.c02_stack import c02_stack
from orion.pipeline.components.c03_iisg import c03_iisg
from orion.pipeline.components.c04_architect import c04_architect
from orion.pipeline.components.c05_planner import c05_planner
from orion.pipeline.components.c06_context import c06_context
from orion.pipeline.components.c07_roles import c07_roles
from orion.pipeline.components.c07_single import c07_single
from orion.pipeline.components.c08_integrator import c08_integrator
from orion.pipeline.components.c09_validation import c09_validation
from orion.pipeline.components.c10_checkpoint import c10_checkpoint
from orion.pipeline.components.c11_executor import c11_executor
from orion.pipeline.components.c12_memory import c12_memory
from orion.pipeline.components.c15_rollback import c15_rollback

logger = logging.getLogger(__name__)


class PipelineRunner:

    PLANNING_MODE_COMPONENTS = [
        c01_intent, c02_stack, c03_iisg, c04_architect, c05_planner,
        c06_context, c07_roles, c08_integrator, c09_validation,
        c10_checkpoint, c11_executor, c12_memory, c15_rollback
    ]  # 13 components (C13/C14 added in next prompt)

    FAST_MODE_COMPONENTS = [
        c01_intent, c02_stack, c06_context, c07_single,
        c09_validation, c11_executor, c12_memory
    ]  # 7 components

    def __init__(self):
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, dict] = {}

    def get_session_default_mode(self) -> RunMode:
        return RunMode.PLANNING

    async def _wait_for_approval(
        self,
        run_id: str,
        approval_type: str,
        timeout_seconds: int = 300
    ) -> dict:
        if run_id not in self._approval_events:
            self._approval_events[run_id] = asyncio.Event()
        try:
            await asyncio.wait_for(
                self._approval_events[run_id].wait(),
                timeout=timeout_seconds
            )
            return self._approval_results.get(run_id, {"decision": "cancel"})
        except asyncio.TimeoutError:
            return {"decision": "cancel"}

    async def resolve_approval(self, run_id: str, decision: dict):
        if run_id not in self._approval_events:
            self._approval_events[run_id] = asyncio.Event()
        self._approval_results[run_id] = decision
        self._approval_events[run_id].set()

    async def _check_cost_gate(self, ctx: PipelineContext):
        budget = settings.SESSION_BUDGET_USD
        total_cost = getattr(ctx, "total_cost_usd", 0.0)
        if total_cost and total_cost >= budget:
            ctx.cancelled = True
            logger.warning(f"Cost gate triggered: {total_cost} >= {budget}")

    async def run(
        self,
        ctx: PipelineContext,
        emit_fn
    ) -> PipelineContext:
        await emit_fn(ctx.session_id, {"type": "pipeline.started", "run_id": ctx.run_id})

        components = (
            self.PLANNING_MODE_COMPONENTS
            if ctx.mode == RunMode.PLANNING
            else self.FAST_MODE_COMPONENTS
        )

        try:
            for component in components:
                if ctx.cancelled or ctx.error:
                    break

                # C12 runs as background task — non-blocking
                if component is c12_memory:
                    asyncio.create_task(component.execute(ctx))
                    continue

                # C15 only runs if there is an error
                if component is c15_rollback:
                    if not ctx.error:
                        continue

                await self._check_cost_gate(ctx)
                if ctx.cancelled:
                    break

                ctx = await component.execute(ctx)

            await emit_fn(
                ctx.session_id,
                {
                    "type": "pipeline.completed" if not ctx.error else "pipeline.failed",
                    "run_id": ctx.run_id,
                    "error": ctx.error
                }
            )

        except Exception as e:
            ctx.error = str(e)
            logger.exception(f"Pipeline crashed on run {ctx.run_id}: {e}")
            await emit_fn(
                ctx.session_id,
                {"type": "pipeline.failed", "run_id": ctx.run_id, "error": ctx.error}
            )

        return ctx


pipeline_runner = PipelineRunner()
