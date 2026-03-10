import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from orion.pipeline.components.c03_iisg import c03_iisg
from orion.pipeline.context import PipelineContext
from orion.schemas.pipeline import RunMode

@pytest.mark.asyncio
async def test_c03_pause_and_wait():
    ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.PLANNING)

    # We mock _wait_for_approval to simulate a pause and immediate user unblocking
    mock_decision = {"approved": True}

    with patch('orion.pipeline.runner.PipelineRunner._wait_for_approval', new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = mock_decision

        result = await c03_iisg.execute(ctx)

        assert mock_wait.called
        assert result.iisg is not None
        assert result.iisg.approved_by_user is True
        assert len(result.iisg.clauses) >= 3

@pytest.mark.asyncio
async def test_c03_skips_in_fast_mode():
    ctx = PipelineContext.create("sess1", "ws1", "test", RunMode.FAST)
    result = await c03_iisg.execute(ctx)
    assert result.iisg is None
