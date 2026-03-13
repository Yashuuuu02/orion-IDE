import asyncio
import json
import logging
import sqlite3
import os
from typing import Any
from pathlib import Path
from fastapi import WebSocket
from orion.llm.manager import llm_manager
from orion.schemas.settings import ProviderConfig
from orion.schemas.pipeline import RunMode
from orion.core.config import settings

logger = logging.getLogger(__name__)

class WebSocketSessionManager:
    def __init__(self):
        self._active_connections: dict[str, Any] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, dict[str, Any]] = {}

        # SQLite path for memory
        self._memory_db_path = Path(os.path.expanduser(settings.SKILL_GLOBAL_PATH)).parent / "memories.db"
        if not self._memory_db_path.exists():
            # Create dummy to avoid sqlite errors if path doesn't exist
            self._memory_db_path = Path(os.path.expanduser("~/.orion/memories.db"))

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self._active_connections[session_id] = websocket

        from orion.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        buffered = []
        async with AsyncSessionLocal() as db:
            await db.execute(text(
                "UPDATE orion_sessions "
                "SET ws_status='active', ws_connected_at=NOW(), ws_last_seen=NOW() "
                "WHERE id=:sid"
            ), {'sid': session_id})
            await db.commit()
            
            result = await db.execute(text(
                "SELECT event_json FROM ws_event_buffer "
                "WHERE session_id=:sid ORDER BY created_at ASC"
            ), {'sid': session_id})
            buffered = [row[0] for row in result.fetchall()]

        if buffered:
            logger.info(f"Replaying {len(buffered)} events for reconnecting session {session_id}")
            for item in buffered:
                try:
                    await websocket.send_text(json.dumps(item) if isinstance(item, dict) else item)
                except Exception as e:
                    logger.error(f"Failed to replay event: {e}")

    def disconnect(self, session_id: str):
        if session_id in self._active_connections:
            self._active_connections.pop(session_id, None)
            logger.info(f"Session {session_id} disconnected. Pipeline running headless if active.")

    async def emit(self, session_id: str, event: dict):
        event_str = json.dumps(event)

        from orion.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text(
                "INSERT INTO ws_event_buffer(session_id, run_id, event_json) VALUES (:sid, :rid, :evt::jsonb)"
            ), {'sid': session_id, 'rid': event.get('run_id'), 'evt': event_str})
            
            await db.execute(text(
                "DELETE FROM ws_event_buffer WHERE id IN ("
                "  SELECT id FROM ws_event_buffer "
                "  WHERE session_id=:sid ORDER BY created_at DESC OFFSET 50"
                ")"
            ), {'sid': session_id})
            await db.commit()

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

    def _resolve_mode(self, message: dict) -> RunMode:
        if message.get("source") == "chat_tab":
            return RunMode.FAST
        try:
            return RunMode(message.get("mode", "planning"))
        except ValueError:
            return RunMode.PLANNING

    async def handle_message(self, session_id: str, message: dict, websocket=None):
        msg_type = message.get("type")

        if msg_type == "run_pipeline":
            mgr = getattr(self, "_llm_manager", llm_manager)
            if not settings.MOCK_LLM and mgr is not None and not mgr.is_configured():
                err: dict[str, str] = {
                    "type": "error",
                    "code": "NO_PROVIDER_CONFIGURED",
                    "action": "open_settings"
                }
                await self.emit(session_id, err)
                return

            run_mode = self._resolve_mode(message)
            raw_prompt = message.get("prompt", "").strip()
            workspace_id = message.get("workspace_id", "default")

            if not raw_prompt:
                await self.emit(session_id, {
                    "type": "error",
                    "code": "EMPTY_PROMPT"
                })
                return

            from orion.pipeline.context import PipelineContext
            from orion.pipeline.runner import PipelineRunner
            from orion.schemas.settings import RunConfig

            ctx = PipelineContext.create(
                session_id=session_id,
                workspace_id=workspace_id,
                raw_prompt=raw_prompt,
                mode=run_mode,
                run_config=RunConfig()
            )

            async def ws_emit(ctx, event_type: str, payload: dict):
                await self.emit(session_id, {
                    "type": event_type,
                    "run_id": ctx.run_id,
                    **payload
                })

            await self.emit(session_id, {
                "type": "pipeline.started",
                "run_id": ctx.run_id,
                "mode": run_mode.value
            })

            runner = PipelineRunner()
            asyncio.create_task(runner.run(ctx, ws_emit))
            logger.info(f"Pipeline task created for session={session_id} run_id={ctx.run_id} mode={run_mode}")

        elif msg_type == "cancel_run":
            run_id = message.get("run_id")
            # In real system, we'd lookup the ctx and set ctx.cancelled = True
            logger.info(f"Cancel run requested for {run_id}")

        elif msg_type in ["approve_iisg", "approve_cost_cap", "dismiss_skill_warning",
                      "approve_plan", "reject_plan"]:
            run_id = str(message.get("run_id", ""))
            approved = msg_type in ["approve_iisg", "approve_cost_cap", "approve_plan"]
            decision = message.get("decision", {"approved": approved})
            if isinstance(decision, dict) and "approved" not in decision:
                decision["approved"] = approved
            self.resolve_approval(session_id, run_id, decision if isinstance(decision, dict) else {"approved": approved})

        elif msg_type == "update_settings":
            providers_data = message.get("providers", [])
            providers = [ProviderConfig(**p) for p in providers_data]
            llm_manager.configure(providers)
            logger.info("Settings updated via WS")

        elif msg_type == "set_tab_state":
            state = message.get("state", {})
            from orion.core.database import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as db:
                await db.execute(text("UPDATE orion_sessions SET tab_state=:state::jsonb WHERE id=:sid"), {'state': json.dumps(state), 'sid': session_id})
                await db.commit()

        elif msg_type == "update_permissions":
            perms = message.get("permissions", {})
            from orion.core.database import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as db:
                await db.execute(text("UPDATE orion_sessions SET permissions=:perms::jsonb WHERE id=:sid"), {'perms': json.dumps(perms), 'sid': session_id})
                await db.commit()

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
