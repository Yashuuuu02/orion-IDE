import pytest
import json
from unittest.mock import patch, AsyncMock
from orion.pipeline.runner import pipeline_runner

@pytest.mark.asyncio
async def test_restore_pending_approvals_no_crash_on_empty():
    mock_redis = AsyncMock()
    mock_redis.keys.return_value = []

    with patch("orion.pipeline.runner.get_redis", return_value=mock_redis):
        # Should not raise any exception
        await pipeline_runner._restore_pending_approvals()

@pytest.mark.asyncio
async def test_restore_pending_approvals_emits_preview():
    mock_redis = AsyncMock()
    mock_redis.keys.return_value = [b"iisg_approval:run-123"]
    mock_redis.get.return_value = json.dumps({"session_id": "test-session", "type": "iisg"}).encode("utf-8")

    with patch("orion.pipeline.runner.get_redis", return_value=mock_redis), \
         patch("orion.api.ws.ws_manager.emit", new_callable=AsyncMock) as mock_emit:

        await pipeline_runner._restore_pending_approvals()

        mock_emit.assert_called_once_with("test-session", {
            "type": "iisg.preview",
            "run_id": "run-123",
            "restored": True,
            "approval_type": "iisg"
        })
