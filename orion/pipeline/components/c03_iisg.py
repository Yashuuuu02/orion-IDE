import logging
import json
import asyncio
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.iisg import IISGContract
from orion.llm.manager import llm_manager
# from orion.pipeline.runner import pipeline_runner # Wait, cyclic if we put it here and mock it. Let's import it locally or mock it.

logger = logging.getLogger(__name__)

class IISGGeneratorComponent(BaseComponent):
    component_id = "c03_iisg"
    component_name = "IISG Generator"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            logger.info("C03: Skipping in FAST mode")
            return ctx

        logger.info("C03: Generating IISG Contract")

        messages = [
            {"role": "system", "content": "You are the IISG Generator. Generate a formal IISGContract with clauses."},
            {"role": "user", "content": f"Intent: {ctx.intent.summary if ctx.intent else ''}"}
        ]

        response_str = await llm_manager.get_completion(
            model=ctx.active_provider or "openai",
            messages=messages,
            max_tokens=4000,
            component_name="c03_iisg"
        )

        parsed = json.loads(response_str)
        ctx.iisg = IISGContract(**parsed)

        # In a real app we'd save it to the DB here

        # PAUSE
        await self._ws_emit(ctx, "iisg.preview", {"contract": ctx.iisg.model_dump()})

        from orion.pipeline.runner import pipeline_runner

        # Blocks until user approves
        try:
            # 5 minute timeout
            decision = await asyncio.wait_for(
                pipeline_runner._wait_for_approval(ctx.run_id, "iisg"),
                timeout=300.0
            )
            if not decision.get("approved"):
                ctx.cancelled = True
                return ctx

            # Re-update the contract to reflect approval
            ctx.iisg.approved_by_user = True

        except asyncio.TimeoutError:
            logger.warning("C03: Approval timed out. Cancelling.")
            ctx.cancelled = True

        except asyncio.CancelledError:
            ctx.cancelled = True

        return ctx

# Expose instance
c03_iisg = IISGGeneratorComponent()
