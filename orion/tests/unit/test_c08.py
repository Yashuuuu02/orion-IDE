import pytest
from unittest.mock import AsyncMock, patch
from orion.pipeline.components.c08_integrator import Integrator
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentRole, AgentOutput, FileChange


@pytest.mark.asyncio
async def test_c08_merges_outputs():
    """Integrator merges successful agent outputs."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    ctx.agent_outputs = [
        AgentOutput(
            agent_role=AgentRole.BACKEND, run_id=ctx.run_id, success=True,
            file_changes=[FileChange(file_path="src/api.py", operation="create", reason="new endpoint")],
            iisg_satisfied=["c1"], tokens_used=200, duration_ms=100,
        ),
        AgentOutput(
            agent_role=AgentRole.TESTING, run_id=ctx.run_id, success=True,
            file_changes=[FileChange(file_path="tests/test_api.py", operation="create", reason="unit test")],
            iisg_satisfied=["c2"], tokens_used=150, duration_ms=80,
        ),
    ]

    comp = Integrator()
    result = await comp.execute(ctx)

    assert result.merged is not None



@pytest.mark.asyncio
async def test_c08_handles_all_failed():
    """If all agents failed, sets error."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    ctx.agent_outputs = [
        AgentOutput(
            agent_role=AgentRole.BACKEND, run_id=ctx.run_id, success=False,
            file_changes=[], iisg_satisfied=[], tokens_used=0, duration_ms=0,
            error="crashed",
        ),
    ]

    comp = Integrator()
    result = await comp.execute(ctx)

    assert result.error == "All agents failed — nothing to integrate"

