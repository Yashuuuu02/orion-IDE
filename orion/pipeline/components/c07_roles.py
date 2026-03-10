import asyncio
import logging
from orion.pipeline.base_component import BaseComponent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentRole, AgentOutput, AgentStatus
from orion.agents.backend import BackendAgent
from orion.agents.frontend import FrontendAgent
from orion.agents.database import DatabaseAgent
from orion.agents.devops import DevOpsAgent
from orion.agents.testing import TestingAgent
from orion.agents.docs import DocsAgent

logger = logging.getLogger(__name__)

# Singleton agent instances (instantiated once, not per run)
AGENT_MAP = {
    AgentRole.BACKEND: BackendAgent(),
    AgentRole.FRONTEND: FrontendAgent(),
    AgentRole.DATABASE: DatabaseAgent(),
    AgentRole.DEVOPS: DevOpsAgent(),
    AgentRole.TESTING: TestingAgent(),
    AgentRole.DOCS: DocsAgent(),
}


class ParallelRoles(BaseComponent):
    component_id = "c07_roles"
    component_name = "Parallel Roles"

    async def _run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.cancelled:
            return ctx

        if ctx.mode == RunMode.FAST:
            logger.info("C07: Skipping parallel roles in FAST mode")
            return ctx

        # Get enabled agents
        enabled_agents = []
        for role, agent in AGENT_MAP.items():
            if ctx.run_config.is_agent_enabled(role):
                enabled_agents.append((role, agent))

        # If no agent_configs specified, default to all agents enabled
        if not enabled_agents and not ctx.run_config.agent_configs:
            enabled_agents = list(AGENT_MAP.items())

        if not enabled_agents:
            logger.warning("C07: No agents enabled in run_config")
            return ctx

        logger.info(f"C07: Running {len(enabled_agents)} agents in parallel")

        # Build tasks — get per-role context string from ctx.contexts
        tasks = []
        role_order = []
        for role, agent in enabled_agents:
            role_key = role.value
            context_str = ""
            if ctx.contexts and isinstance(ctx.contexts, dict):
                context_str = ctx.contexts.get(role_key, ctx.contexts.get("orion_md", ""))
            tasks.append(agent.run(ctx, context_str))
            role_order.append(role)

        # Run all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        outputs: list[AgentOutput] = []
        total_tokens = 0

        for role, result in zip(role_order, results):
            if isinstance(result, Exception):
                logger.error(f"C07: Agent {role.value} failed: {result}")
                output = AgentOutput(
                    agent_role=role,
                    run_id=ctx.run_id,
                    success=False,
                    file_changes=[],
                    iisg_satisfied=[],
                    tokens_used=0,
                    duration_ms=0,
                    error=str(result),
                )
            else:
                output = result
                logger.info(f"C07: Agent {role.value} completed, tokens={output.tokens_used}")

            outputs.append(output)
            total_tokens += output.tokens_used

            await self._ws_emit(ctx, "agent.status", {
                "role": role.value,
                "status": "completed" if output.success else "failed",
                "tokens_used": output.tokens_used,
            })

        ctx.agent_outputs = outputs

        await self._ws_emit(ctx, "agent.token_update", {
            "total_tokens": total_tokens,
        })

        return ctx


c07_roles = ParallelRoles()
