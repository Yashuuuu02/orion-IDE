import pytest
from unittest.mock import AsyncMock

@pytest.fixture(autouse=True)
def mock_ws_emit(monkeypatch):
    """Globally mock WebSocket event emission to prevent tests from needing a running Redis server."""
    monkeypatch.setattr('orion.api.ws.WebSocketSessionManager.emit', AsyncMock())
