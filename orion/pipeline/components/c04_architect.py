import json
import logging
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.llm.manager import llm_manager

logger = logging.getLogger(__name__)

class Architect(BaseComponent):
    component_id = "c04_architect"
    component_name = "Architect"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            logger.info("C04: Skipping in FAST mode")
            return ctx

        logger.info("C04: Selecting architectural patterns")

        messages = [
            {"role": "system", "content": "You are the Architect. Generate architectural blueprint dict."},
            {"role": "user", "content": f"Based on IISG: {ctx.iisg.contract_id if ctx.iisg else ''}"}
        ]

        response_str = await llm_manager.get_completion(
            model=ctx.active_provider or "openai",
            messages=messages,
            max_tokens=2000,
            component_name="c04_architect"
        )

        ctx.blueprint = json.loads(response_str)
        return ctx

# Expose instance
c04_architect = Architect()
