import logging
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentRole
from orion.agents.single import SingleAgent

logger = logging.getLogger(__name__)

# Role mapping for intent-based selection
ROLE_KEYWORDS = {
    AgentRole.BACKEND: ["backend", "api", "server", "endpoint", "route"],
    AgentRole.FRONTEND: ["frontend", "ui", "component", "react", "css"],
    AgentRole.DATABASE: ["database", "db", "schema", "migration", "sql"],
    AgentRole.DEVOPS: ["devops", "deploy", "docker", "ci", "cd", "infra"],
    AgentRole.TESTING: ["test", "testing", "spec", "coverage"],
    AgentRole.DOCS: ["docs", "documentation", "readme", "comment"],
}


class FastModeSingleAgent(BaseComponent):
    component_id = "c07_single"
    component_name = "Fast Mode Single Agent"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode != RunMode.FAST:
            logger.info("C07 Single: Skipping — not in FAST mode")
            return ctx

        # Pick the most relevant role based on ctx.intent.affected_roles
        selected_role = AgentRole.BACKEND  # default
        if ctx.intent and ctx.intent.affected_roles:
            for role_str in ctx.intent.affected_roles:
                try:
                    selected_role = AgentRole(role_str)
                    break
                except ValueError:
                    continue

        logger.info(f"C07 Single: Running SingleAgent as {selected_role.value}")

        agent = SingleAgent()
        agent.role = selected_role

        context_str = ""
        if ctx.contexts and isinstance(ctx.contexts, dict):
            context_str = ctx.contexts.get(selected_role.value, ctx.contexts.get("orion_md", ""))

        result = await agent.run(ctx, context_str)
        ctx.agent_outputs = [result]

        await self._ws_emit(ctx, "agent.status", {
            "role": selected_role.value,
            "status": "completed" if result.success else "failed",
            "tokens_used": result.tokens_used,
        })

        return ctx


c07_single = FastModeSingleAgent()

# Alias for backward compatibility
SingleAgentComponent = FastModeSingleAgent
