import pytest
import asyncio
import time
from orion.pipeline.components.c12_memory import MemoryAndLogging
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode
from orion.schemas.agent import AgentRole, AgentOutput


@pytest.mark.asyncio
async def test_c12_does_not_block():
    """Pipeline total time is not affected by C12 (fire-and-forget)."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.PLANNING)
    ctx.agent_outputs = [
        AgentOutput(
            agent_role=AgentRole.BACKEND, run_id=ctx.run_id, success=True,
            file_changes=[], iisg_satisfied=[], tokens_used=100, duration_ms=50,
        )
    ]

    comp = MemoryAndLogging()

    start = time.time()
    result = await comp.execute(ctx)
    elapsed = time.time() - start

    # The execute call should return almost instantly since background task is fire-and-forget
    assert elapsed < 1.0, f"FAIL: C12 blocked for {elapsed:.2f}s"
    print(f"ok: C12 returned in {elapsed*1000:.0f}ms — does not block pipeline")

    # Give background task a chance to run
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_c12_handles_empty_outputs():
    """C12 handles ctx with no agent outputs gracefully."""
    ctx = PipelineContext.create("s1", "w1", "test", RunMode.FAST)
    ctx.agent_outputs = []

    comp = MemoryAndLogging()
    result = await comp.execute(ctx)

    # Should not crash
    assert result is not None
    print("ok: C12 handles empty outputs gracefully")
    await asyncio.sleep(0.1)
