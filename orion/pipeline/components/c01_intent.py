import json
import logging
from typing import Optional
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.intent import IntentObject
from orion.llm.manager import llm_manager

logger = logging.getLogger(__name__)

class IntentInterpreter(BaseComponent):
    component_id = "c01_intent"
    component_name = "Intent Interpreter"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        # Intent cache was removed as part of Redis dropout
        logger.info("C01: Calling LLM.")

        # Prepare LLM call
        messages = [
            {"role": "system", "content": "You are the Intent Interpreter. Return JSON matching the IntentObject schema."},
            {"role": "user", "content": f"Parse this intent: {ctx.raw_prompt}"}
        ]

        # We need the active provider's config to get token limit, but BaseAgent did something similar
        # For components, the arch doc implies calling llm_manager directly
        # We are using get_completion with component_name for mock resolution
        response_str = await llm_manager.get_completion(
            model=ctx.active_provider or "openai", # Dummy routing
            messages=messages,
            max_tokens=2000,
            component_name="c01_intent"
        )

        parsed = json.loads(response_str)
        ctx.intent = IntentObject(**parsed)

        return ctx

# Expose instance
c01_intent = IntentInterpreter()
