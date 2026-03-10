import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from orion.pipeline.components.c07_roles import ParallelRoles
from orion.pipeline.components.c07_single import FastModeSingleAgent
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentRole, AgentOutput, AgentStatus
from orion.schemas.settings import RunConfig, AgentRunConfig
from orion.schemas.intent import IntentObject, IntentType


@pytest.mark.asyncio
async def test_c07_parallel_all_agents_run():
    """All 6 agents run, one failure does not cancel others."""
    # Enable all 6 agents
    agent_configs = [
        AgentRunConfig(role=AgentRole.BACKEND, enabled=True, token_limit=50000),
        AgentRunConfig(role=AgentRole.FRONTEND, enabled=True, token_limit=50000),
        AgentRunConfig(role=AgentRole.DATABASE, enabled=True, token_limit=30000),
        AgentRunConfig(role=AgentRole.DEVOPS, enabled=True, token_limit=30000),
        AgentRunConfig(role=AgentRole.TESTING, enabled=True, token_limit=40000),
        AgentRunConfig(role=AgentRole.DOCS, enabled=True, token_limit=20000),
    ]
    run_config = RunConfig(agent_configs=agent_configs)
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING, run_config=run_config)
    ctx.contexts = {"orion_md": "test context"}

    comp = ParallelRoles()

    # Make one agent raise, others succeed
    call_count = 0
    async def mock_agent_run(agent_ctx, context_str):
        nonlocal call_count
        call_count += 1
        if call_count == 3:  # 3rd agent fails
            raise RuntimeError("Simulated agent failure")
        return AgentOutput(
            agent_role=AgentRole.BACKEND,
            run_id=ctx.run_id,
            success=True,
            file_changes=[],
            iisg_satisfied=[],
            tokens_used=100,
            duration_ms=50,
        )

    # Patch all agents in AGENT_MAP
    with patch('orion.pipeline.components.c07_roles.AGENT_MAP') as mock_map:
        mock_agents = {}
        for role in AgentRole:
            agent = MagicMock()
            agent.run = mock_agent_run
            mock_agents[role] = agent
        mock_map.items.return_value = mock_agents.items()

        result = await comp.execute(ctx)

    assert len(result.agent_outputs) == 6, f"Expected 6 outputs, got {len(result.agent_outputs)}"
    failed = [o for o in result.agent_outputs if not o.success]
    succeeded = [o for o in result.agent_outputs if o.success]
    assert len(failed) == 1, f"Expected exactly 1 failure, got {len(failed)}"
    assert len(succeeded) == 5, f"Expected 5 successes, got {len(succeeded)}"
    print("ok: all 6 agents run, one failure does not cancel others")


@pytest.mark.asyncio
async def test_c07_fast_mode_single_agent():
    """Single agent runs in fast mode, result stored correctly."""
    run_config = RunConfig()
    ctx = PipelineContext.create("s1", "w1", "fix login bug", RunMode.FAST, run_config=run_config)
    ctx.intent = IntentObject(
        intent_hash="abc", intent_type=IntentType.BUG_FIX,
        summary="fix login", affected_files=[], affected_roles=["backend"],
        complexity=2, requires_iisg=False, raw_prompt="fix login bug",
    )
    ctx.contexts = {"backend": "some context", "orion_md": ""}

    comp = FastModeSingleAgent()

    mock_output = AgentOutput(
        agent_role=AgentRole.BACKEND,
        run_id=ctx.run_id,
        success=True,
        file_changes=[],
        iisg_satisfied=[],
        tokens_used=500,
        duration_ms=200,
    )

    with patch('orion.pipeline.components.c07_single.SingleAgent') as MockSingle:
        instance = MockSingle.return_value
        instance.run = AsyncMock(return_value=mock_output)

        result = await comp.execute(ctx)

    assert len(result.agent_outputs) == 1
    assert result.agent_outputs[0].success is True
    assert result.agent_outputs[0].tokens_used == 500
    print("ok: single agent runs in fast mode, result stored correctly")
