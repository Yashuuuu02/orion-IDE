import logging
from orion.pipeline.context import PipelineContext
from orion.llm.manager import llm_manager

logger = logging.getLogger(__name__)

class C14FailureAnalysis:
    """
    Component 14: Failure Analysis
    Only runs when ctx.error is set. Uses the LLM to analyze the failure
    and determine a recovery strategy.
    """
    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.error:
            # If ctx.error is None: return ctx immediately without doing anything
            return ctx

        try:
            # Gather context for LLM
            error_msg = str(ctx.error)
            val_failures = ""
            if ctx.validation and not ctx.validation.is_valid:
                val_failures = "\n".join(ctx.validation.errors)

            iisg_clauses = ""
            if ctx.iisg:
                iisg_clauses = str(ctx.iisg.model_dump())

            prompt = f"""Analyze the following pipeline failure and recommend a recovery strategy.

Error: {error_msg}
Validation Failures: {val_failures}
IISG Clauses: {iisg_clauses}

Output EXACTLY ONE of the following strategies (just the word):
- retry
- rollback
- partial_rollback
- user_input_required
"""
            messages = [{"role": "user", "content": prompt}]

            # Use planning model (fastest available that is smart enough for analysis)
            response = await llm_manager.get_completion(
                model=ctx.run_config.model_planning if hasattr(ctx.run_config, "model_planning") else "default",
                messages=messages,
                max_tokens=20,
                component_name="c14_failure"
            )

            raw_response = response.strip().lower()

            valid_strategies = {"retry", "rollback", "partial_rollback", "user_input_required"}

            # Map robustly to a valid strategy
            strategy = "user_input_required" # default fallback
            # Sort by length descending to match partial_rollback before rollback
            for valid in sorted(valid_strategies, key=len, reverse=True):
                if valid in raw_response:
                    strategy = valid
                    break

            ctx.recovery_strategy = strategy
            logger.info(f"[C14] Failure Analysis set recovery strategy for {ctx.run_id}: {strategy}")

        except Exception as e:
            logger.error(f"[C14] Failure analysis crashed {ctx.run_id}: {e}")
            ctx.recovery_strategy = "user_input_required"

        return ctx

c14_failure = C14FailureAnalysis()
