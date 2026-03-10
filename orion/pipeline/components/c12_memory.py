import asyncio
import logging
import time
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class MemoryAndLogging(BaseComponent):
    component_id = "c12_memory"
    component_name = "Memory & Logging"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        # Fire and forget — NEVER block the pipeline
        asyncio.create_task(self._background_write(ctx))
        logger.info("C12: Background logging task scheduled (fire-and-forget)")
        return ctx

    async def _background_write(self, ctx: PipelineContext):
        """Write logging data to PostgreSQL. Runs as background task."""
        try:
            # In production, these would be actual DB writes
            # pipeline_runs: update status, completed_at, cost_actual
            run_data = {
                "run_id": ctx.run_id,
                "status": "completed" if not ctx.error else "failed",
                "completed_at": time.time(),
                "cost_actual": ctx.cost_actual,
                "error": ctx.error,
            }
            logger.debug(f"C12: Logged pipeline run: {run_data['run_id']}")

            # agent_executions: one row per agent
            for output in ctx.agent_outputs:
                agent_data = {
                    "run_id": ctx.run_id,
                    "agent_role": output.agent_role.value,
                    "success": output.success,
                    "tokens_used": output.tokens_used,
                    "duration_ms": output.duration_ms,
                    "error": output.error,
                }
                logger.debug(f"C12: Logged agent execution: {agent_data['agent_role']}")

            # validation_results: one row
            if ctx.validation:
                val_data = {
                    "run_id": ctx.run_id,
                    "passed": ctx.validation.passed,
                    "total_duration_ms": ctx.validation.total_duration_ms,
                    "layer_count": len(ctx.validation.layers),
                }
                logger.debug(f"C12: Logged validation: passed={val_data['passed']}")

            # cost_tracking: one row
            total_tokens = sum(o.tokens_used for o in ctx.agent_outputs)
            cost_data = {
                "run_id": ctx.run_id,
                "total_tokens": total_tokens,
                "cost_usd": ctx.cost_actual,
            }
            logger.debug(f"C12: Logged cost tracking: {cost_data['total_tokens']} tokens")

        except Exception as e:
            # Background task — log error but never crash pipeline
            logger.error(f"C12: Background logging failed: {e}")


c12_memory = MemoryAndLogging()
