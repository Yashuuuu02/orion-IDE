import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

from orion.api.ws import WebSocketSessionManager
from orion.core.redis_client import get_redis

# Mock FastAPI WebSocket
class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_text(self, data):
        self.sent_messages.append(data)

@pytest.fixture
def ws_manager():
    return WebSocketSessionManager()

@pytest.fixture
def mock_ws():
    return MockWebSocket()

@pytest.fixture
def mock_redis():
    class MockRedis:
        def __init__(self):
            self.lists = {}
            self.hashes = {}

        async def lrange(self, key, start, end):
            return self.lists.get(key, [])[start:end+1 if end != -1 else None]

        async def rpush(self, key, value):
            if key not in self.lists:
                self.lists[key] = []
            self.lists[key].append(value)

        async def ltrim(self, key, start, end):
            if key in self.lists:
                if end == -1:
                    self.lists[key] = self.lists[key][start:]
                else:
                    self.lists[key] = self.lists[key][start:end+1]

        async def expire(self, key, time):
            pass

        async def hset(self, key, mapping):
            if key not in self.hashes:
                self.hashes[key] = {}
            self.hashes[key].update(mapping)

    return MockRedis()

@pytest.mark.asyncio
async def test_connect(ws_manager, mock_ws, mock_redis):
    with patch('orion.api.ws.get_redis', return_value=mock_redis):
        await ws_manager.connect("session_1", mock_ws)
        assert mock_ws.accepted
        assert "session_1" in ws_manager._active_connections

@pytest.mark.asyncio
async def test_disconnect(ws_manager, mock_ws, mock_redis):
    with patch('orion.api.ws.get_redis', return_value=mock_redis):
        await ws_manager.connect("session_1", mock_ws)
        ws_manager.disconnect("session_1")
        assert "session_1" not in ws_manager._active_connections

@pytest.mark.asyncio
async def test_emit_while_disconnected_buffers(ws_manager, mock_redis):
    with patch('orion.api.ws.get_redis', return_value=mock_redis):
        # Emit without connecting
        await ws_manager.emit("session_1", {"type": "test_event"})

        # Check buffer
        buffer_key = "ws_session:session_1:events"
        buffered = await mock_redis.lrange(buffer_key, 0, -1)
        assert len(buffered) == 1
        assert json.loads(buffered[0])["type"] == "test_event"

@pytest.mark.asyncio
async def test_replay_on_reconnect(ws_manager, mock_ws, mock_redis):
    with patch('orion.api.ws.get_redis', return_value=mock_redis):
        # Buffer an event first
        await ws_manager.emit("session_1", {"type": "buffered_event"})

        # Now connect
        await ws_manager.connect("session_1", mock_ws)

        # Check it was replayed
        assert len(mock_ws.sent_messages) == 1
        assert json.loads(mock_ws.sent_messages[0])["type"] == "buffered_event"

@pytest.mark.asyncio
async def test_no_provider_gate(ws_manager, mock_ws, mock_redis):
    # Setup mock LLM manager to return False for configured mapping and mock
    with patch('orion.api.ws.get_redis', return_value=mock_redis), \
         patch('orion.api.ws.llm_manager.is_configured', return_value=False), \
         patch('orion.api.ws.settings.MOCK_LLM', False):

        await ws_manager.connect("session_1", mock_ws)

        # Send run_pipeline
        msg = {"type": "run_pipeline"}
        await ws_manager.handle_message("session_1", msg)

        # Check response
        assert len(mock_ws.sent_messages) == 1
        response = json.loads(mock_ws.sent_messages[0])
        assert response["type"] == "error"
        assert response["code"] == "NO_PROVIDER_CONFIGURED"

@pytest.mark.asyncio
async def test_fast_mode_chat_tab_override(ws_manager, mock_ws, mock_redis):
    with patch('orion.api.ws.get_redis', return_value=mock_redis), \
         patch('orion.api.ws.llm_manager.is_configured', return_value=True):

        await ws_manager.connect("session_1", mock_ws)

        # Send run_pipeline from chat tab with PLANNING mode mapping initially
        msg = {
            "type": "run_pipeline",
            "mode": "planning",
            "source": "chat_tab"
        }

        # Should be intercepted.
        with patch('orion.api.ws.logger.info') as mock_log:
            await ws_manager.handle_message("session_1", msg)
            mock_log.assert_any_call("Pipeline started for session_1 in mode RunMode.FAST")
