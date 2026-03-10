import pytest
from unittest.mock import patch, AsyncMock
from orion.pipeline.components.c05_planner import c05_planner
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode

@pytest.mark.asyncio
async def test_c05_cost_estimate():
    ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.PLANNING)
    ctx.run_config.cost_cap_usd = 10.0 # high enough to avoid prompt pause

    # We mock _check_cost_gate to skip DB
    with patch('orion.pipeline.runner.PipelineRunner._check_cost_gate', new_callable=AsyncMock) as mock_gate:
        result = await c05_planner.execute(ctx)

        assert result.task_dag is not None
        assert "nodes" in result.task_dag
        assert result.cost_estimate is not None
        # From our fixture, task DAG json includes cost_estimate=0.04
        # Or it dynamically assigns it via math
        assert result.cost_estimate > 0.0

@pytest.mark.asyncio
async def test_c05_cost_cap_exceeded_cancels():
    ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.PLANNING)
    ctx.run_config.cost_cap_usd = 0.001 # Extremely low limit to trigger block

    # Simulate user rejection on cost
    mock_decision = {"approved": False}
    with patch('orion.pipeline.runner.PipelineRunner._wait_for_approval', new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = mock_decision

        result = await c05_planner.execute(ctx)

        assert mock_wait.called
        assert result.cancelled is True
