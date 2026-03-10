import asyncio
import json
import logging
import sqlite3
import os
from pathlib import Path
from fastapi import WebSocket
from orion.core.redis_client import get_redis
from orion.llm.manager import llm_manager
from orion.schemas.settings import ProviderConfig
from orion.schemas.pipeline import RunMode
from orion.core.config import settings

logger = logging.getLogger(__name__)

class WebSocketSessionManager:
    def __init__(self):
        self._active_connections: dict[str, WebSocket] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, dict] = {}

        # SQLite path for memory
        self._memory_db_path = Path(os.path.expanduser(settings.SKILL_GLOBAL_PATH)).parent / "memories.db"
        if not self._memory_db_path.exists():
            # Create dummy to avoid sqlite errors if path doesn't exist
            self._memory_db_path = Path(os.path.expanduser("~/.orion/memories.db"))

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self._active_connections[session_id] = websocket

        redis = get_redis()
        # Replay buffered events (max 50)
        buffer_key = f"ws_session:{session_id}:events"
        buffered = await redis.lrange(buffer_key, 0, 49)

        if buffered:
            logger.info(f"Replaying {len(buffered)} events for reconnecting session {session_id}")
            # we want oldest first for replay usually, but Redis lrange returns oldest first if lpush/rpush are used correctly
            # we assume rpush below, so index 0 is oldest.
            for item in buffered:
                try:
                    await websocket.send_text(item)
                except Exception as e:
                    logger.error(f"Failed to replay event: {e}")

    def disconnect(self, session_id: str):
        if session_id in self._active_connections:
            del self._active_connections[session_id]
            logger.info(f"Session {session_id} disconnected. Pipeline running headless if active.")

    async def emit(self, session_id: str, event: dict):
        event_str = json.dumps(event)

        # Always buffer to Redis
        redis = get_redis()
        buffer_key = f"ws_session:{session_id}:events"
        await redis.rpush(buffer_key, event_str)
        await redis.ltrim(buffer_key, -50, -1)  # keep only last 50
        await redis.expire(buffer_key, 7200)    # TTL 2h

        # Send to connected client if present
        if session_id in self._active_connections:
            try:
                await self._active_connections[session_id].send_text(event_str)
            except Exception as e:
                logger.error(f"Failed to emit to {session_id}: {e}")
                self.disconnect(session_id)

    def resolve_approval(self, session_id: str, run_id: str, decision: dict):
        if run_id in self._approval_events:
            self._approval_results[run_id] = decision
            self._approval_events[run_id].set()
            logger.info(f"Approval resolved for run_id {run_id}")

    async def handle_message(self, session_id: str, message: dict):
        msg_type = message.get("type")

        if msg_type == "run_pipeline":
            # NO_PROVIDER_CONFIGURED gate
            if not llm_manager.is_configured() and not settings.MOCK_LLM:
                await self.emit(session_id, {
                    "type": "error",
                    "code": "NO_PROVIDER_CONFIGURED",
                    "action": "open_settings"
                })
                return

            run_mode = message.get("mode", RunMode.PLANNING)
            # CHAT TAB FAST MODE OVERRIDE
            if message.get("source") == "chat_tab":
                run_mode = RunMode.FAST

            # Pipeline starting logic would go here
            logger.info(f"Pipeline started for {session_id} in mode {run_mode}")

        elif msg_type == "cancel_run":
            run_id = message.get("run_id")
            # In real system, we'd lookup the ctx and set ctx.cancelled = True
            logger.info(f"Cancel run requested for {run_id}")

        elif msg_type in ["approve_iisg", "approve_cost_cap", "dismiss_skill_warning"]:
            run_id = message.get("run_id")
            decision = message.get("decision", {})
            self.resolve_approval(session_id, run_id, decision)

        elif msg_type == "update_settings":
            providers_data = message.get("providers", [])
            providers = [ProviderConfig(**p) for p in providers_data]
            llm_manager.configure(providers)
            logger.info("Settings updated via WS")

        elif msg_type == "set_tab_state":
            state = message.get("state", {})
            redis = get_redis()
            await redis.hset(f"ws_session:{session_id}", mapping={"tab_state": json.dumps(state)})

        elif msg_type == "update_permissions":
            perms = message.get("permissions", {})
            redis = get_redis()
            await redis.hset(f"ws_session:{session_id}", mapping={"permissions": json.dumps(perms)})

        elif msg_type == "add_memory":
            content = message.get("content")
            if content:
                import uuid
                conn = sqlite3.connect(self._memory_db_path)
                conn.execute("INSERT INTO memories (id, content) VALUES (?, ?)", (str(uuid.uuid4()), content))
                conn.commit()
                conn.close()
                await self.emit(session_id, {"type": "memory_added"})

        elif msg_type == "delete_memory":
            memory_id = message.get("memory_id")
            if memory_id:
                conn = sqlite3.connect(self._memory_db_path)
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
                conn.close()
                await self.emit(session_id, {"type": "memory_deleted"})

        elif msg_type == "search_query":
            logger.info("search_query not implemented")

        elif msg_type == "ping":
            await self.emit(session_id, {"type": "pong"})

# Singleton instance
ws_manager = WebSocketSessionManager()
