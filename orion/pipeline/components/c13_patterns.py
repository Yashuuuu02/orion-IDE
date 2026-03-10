import logging
import asyncio
from orion.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)

class C13PatternRecognition:
    """
    Component 13: Pattern Recognition
    Runs as a background task to analyze pipeline context for patterns.
    Never blocks the pipeline, never sets ctx.error, returns ctx unchanged.
    """
    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        try:
            # Reads ctx.agent_outputs and ctx.validation
            outputs_count = len(ctx.agent_outputs) if ctx.agent_outputs else 0
            has_validation = ctx.validation is not None

            # Extract and store patterns
            await self._store_patterns(ctx)

            # Logs findings
            logger.info(f"[C13] Pattern Recognition run for {ctx.run_id}: analyzed {outputs_count} outputs, validation present: {has_validation}")

        except Exception as e:
            # We purposely swallow exceptions here so this background task never crashes the pipeline
            logger.error(f"[C13] Background pattern recognition failed for {ctx.run_id}: {e}")

        return ctx

    async def _store_patterns(self, ctx: PipelineContext):
        try:
            from orion.core.database import async_session_maker
            from orion.models.pattern import PatternLibrary

            patterns = self._extract_patterns(ctx)
            if not patterns:
                return

            async with async_session_maker() as session:
                for pattern in patterns:
                    entry = PatternLibrary(
                        run_id=ctx.run_id,
                        session_id=ctx.session_id,
                        pattern_type=pattern["type"],
                        pattern_data=pattern["data"]
                    )
                    session.add(entry)
                await session.commit()
                logger.info(f"C13: stored {len(patterns)} patterns for run {ctx.run_id}")
        except Exception as e:
            logger.warning(f"C13: pattern store failed (non-fatal): {e}")

    def _extract_patterns(self, ctx: PipelineContext) -> list[dict]:
        patterns = []

        # Pattern 1: successful agent outputs
        for output in (ctx.agent_outputs or []):
            if output.success:
                patterns.append({
                    "type": "agent_success",
                    "data": {
                        "agent_role": output.agent_role.value if hasattr(output.agent_role, "value") else str(output.agent_role),
                        "files_changed": len(output.file_changes),
                        "tokens_used": output.tokens_used
                    }
                })
            else:
                patterns.append({
                    "type": "agent_failure",
                    "data": {
                        "agent_role": output.agent_role.value if hasattr(output.agent_role, "value") else str(output.agent_role),
                        "error": output.error
                    }
                })

        # Pattern 2: validation failures
        if ctx.validation and not ctx.validation.passed:
            for layer in ctx.validation.layers:
                if not layer.passed:
                    patterns.append({
                        "type": "validation_failure",
                        "data": {
                            "layer": layer.layer,
                            "issues": layer.issues
                        }
                    })

        return patterns


c13_patterns = C13PatternRecognition()
