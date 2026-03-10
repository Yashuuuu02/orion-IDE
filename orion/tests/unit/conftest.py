import pytest
from unittest.mock import AsyncMock

@pytest.fixture(autouse=True)
def mock_ws_emit(monkeypatch, request):
    """Globally mock WebSocket event emission to prevent tests from needing a running Redis server.
    Skipped for test_ws.py tests which specifically test emit/buffer behaviour."""
    if request.fspath.basename == "test_ws.py":
        return  # Let test_ws.py manage its own mocking
    monkeypatch.setattr('orion.api.ws.WebSocketSessionManager.emit', AsyncMock())
