import json
import logging
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentOutput
from orion.llm.manager import llm_manager

logger = logging.getLogger(__name__)


class Integrator(BaseComponent):
    component_id = "c08_integrator"
    component_name = "Integrator"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            # In fast mode, just take the single agent output as merged
            if ctx.agent_outputs:
                output = ctx.agent_outputs[0]
                ctx.merged = {
                    "file_changes": [fc.model_dump() for fc in output.file_changes],
                    "agents": [output.agent_role.value],
                }
            return ctx

        logger.info("C08: Integrating agent outputs")

        # Collect successful outputs
        successful = [o for o in ctx.agent_outputs if o.success]
        failed = [o for o in ctx.agent_outputs if not o.success]

        if not successful:
            ctx.error = "All agents failed — nothing to integrate"
            return ctx

        # Collect all file changes
        all_changes: dict[str, list[dict]] = {}
        for output in successful:
            for fc in output.file_changes:
                if fc.file_path not in all_changes:
                    all_changes[fc.file_path] = []
                all_changes[fc.file_path].append({
                    "agent": output.agent_role.value,
                    "operation": fc.operation,
                    "content": fc.content,
                    "diff": fc.diff,
                    "reason": fc.reason,
                })

        # Call LLM to merge conflicts
        messages = [
            {"role": "system", "content": "You are the Integrator. Merge agent file changes into a coherent set. Return JSON."},
            {"role": "user", "content": json.dumps({
                "changes": all_changes,
                "iisg_clauses": [c.model_dump() for c in ctx.iisg.clauses] if ctx.iisg else [],
            })},
        ]

        response_str = await llm_manager.get_completion(
            model=ctx.active_provider or "openai",
            messages=messages,
            max_tokens=4000,
            component_name="c08_integrator",
        )

        merged = json.loads(response_str)
        ctx.merged = merged

        # Check IISG satisfaction
        if ctx.iisg:
            satisfied_ids = set()
            for output in successful:
                satisfied_ids.update(output.iisg_satisfied)

            unsatisfied = [c for c in ctx.iisg.clauses if c.clause_id not in satisfied_ids and c.required]
            if unsatisfied:
                clause_ids = [c.clause_id for c in unsatisfied]
                ctx.error = f"IISG clauses not satisfied: {clause_ids}"
                logger.warning(f"C08: {ctx.error}")

        return ctx


c08_integrator = Integrator()
