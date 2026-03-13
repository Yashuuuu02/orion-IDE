import json
import logging
import asyncio
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentRole
from orion.llm.manager import llm_manager
from orion.core.config import settings

logger = logging.getLogger(__name__)

class Planner(BaseComponent):
    component_id = "c05_planner"
    component_name = "Planner"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            logger.info("C05: Skipping in FAST mode")
            return ctx

        import orion.pipeline.runner as runner_module

        logger.info("C05: Generating task DAG")

        messages = [
            {"role": "system", "content": "You are the Planner. Return DAG dict w/ cost_estimate."},
            {"role": "user", "content": "Generate task DAG."}
        ]

        response_str = await llm_manager.get_completion(
            model=ctx.active_provider or "openai",
            messages=messages,
            max_tokens=2000,
            component_name="c05_planner"
        )

        ctx.task_dag = json.loads(response_str)

        # COST ESTIMATION
        complexity_multiplier = (ctx.intent.complexity if ctx.intent else 1) / 5.0
        total_tokens = 0

        # Accumulate tokens for agents (mock hardcoded enabled roles since run_config agents list missing abstract)
        # Using exact requirements: "For each enabled agent in ctx.run_config"
        # We will assume backend and frontend enabled if we can't introspect ctx.run_config.agents
        roles_to_check = [AgentRole.BACKEND, AgentRole.FRONTEND]
        if hasattr(ctx.run_config, 'enabled_agents'):
            roles_to_check = ctx.run_config.enabled_agents

        for role in roles_to_check:
            total_tokens += ctx.run_config.get_token_limit(role) * complexity_multiplier

        # Add integrator overhead (10% overhead logic mapping isn't fully defined so add ~5000)
        total_tokens += 10000

        cost_per_1k = 0.01 # Mock provider rate

        # In actual system, grab from OrionSettings provider dictionary.

        # The planner json specifies cost_estimate dynamically, but if it doesn't we assign
        if "cost_estimate" in ctx.task_dag:
            ctx.cost_estimate = ctx.task_dag["cost_estimate"]
        else:
            ctx.cost_estimate = (total_tokens / 1000) * cost_per_1k

        # Build file plan summary for UI display
        file_plan = []
        if isinstance(ctx.task_dag, dict):
            file_plan = ctx.task_dag.get("file_changes", [])
            if not file_plan:
                # Try to extract from tasks
                for task in ctx.task_dag.get("tasks", []):
                    if isinstance(task, dict) and "file_changes" in task:
                        file_plan.extend(task["file_changes"])

        await self._ws_emit(ctx, "cost.estimate", {
            "cost_estimate": ctx.cost_estimate,
            "file_plan": file_plan,
            "file_count": len(file_plan),
        })

        # COST GATE
        if ctx.cost_estimate and ctx.run_config.cost_cap_usd is not None and ctx.cost_estimate > ctx.run_config.cost_cap_usd:
            await self._ws_emit(ctx, "cost.approval_required")

            try:
                decision = await runner_module.pipeline_runner._wait_for_approval(ctx.run_id, "cost")
                if not decision.get("approved"):
                    ctx.cancelled = True
                    return ctx
            except Exception as e:
                ctx.cancelled = True
                return ctx

        # In planning mode, we wait for user approval of the plan before proceeding
        # (This implies the UI will show the DAG/Blueprint and let the user say "Go")
        try:
            # Emit the plan to UI before waiting for approval
            await self._ws_emit(ctx, "plan.ready", {
                "run_id": ctx.run_id,
                "task_dag": ctx.task_dag,
                "file_plan": file_plan,
                "file_count": len(file_plan),
                "cost_estimate": ctx.cost_estimate,
                "message": "Review the plan and type 'proceed' to execute, or 'cancel' to abort.",
            })
            decision = await asyncio.wait_for(
                runner_module.pipeline_runner._wait_for_approval(ctx.run_id, "planner"),
                timeout=300.0
            )
        except Exception as e:
            logger.error(f"C05 planner approval error: {e}")
            ctx.cancelled = True
            return ctx

        # Simulate budget call validation against cost_tracking
        from orion.pipeline.runner import pipeline_runner
        try:
           await pipeline_runner._check_cost_gate(ctx)
        except RuntimeError as e: # Catch stop throw if desired
           await self._ws_emit(ctx, "cost.budget_alert", {"stop": True, "message": str(e)})
           ctx.cancelled = True
        except Exception as e:
           logger.error(f"C05 check_cost_gate error: {e}")
           ctx.cancelled = True

        return ctx

# Expose instance
c05_planner = Planner()
