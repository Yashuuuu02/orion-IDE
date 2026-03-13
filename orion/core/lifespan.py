from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from orion.core.database import create_all_tables, engine
from orion.pipeline.runner import pipeline_runner
import logging
from alembic import command
from alembic.config import Config
import asyncio

logger = logging.getLogger(__name__)

def run_upgrade(*args: Any, **kwargs: Any) -> None:
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        logger.warning(f"Alembic upgrade skipped or failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect DB, connect Redis, run alembic upgrade head, log ready
    logger.info("Starting Orion FastAPI application...")
    try:
        from orion.core.cleanup import start_cleanup_task
        await create_all_tables()
        app.state.cleanup_task = await start_cleanup_task()
        await pipeline_runner._restore_pending_approvals()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_upgrade)

        # Auto-configure LLM if OpenRouter key is present in environment
        if settings.OPENROUTER_API_KEY:
            from orion.llm.manager import llm_manager
            from orion.schemas.settings import ProviderConfig
            llm_manager.configure([ProviderConfig(
                provider="openrouter",
                model_planning="openrouter/anthropic/claude-3.5-sonnet",
                model_fast="openrouter/openai/gpt-4o-mini",
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                enabled=True,
            )])
            logger.info("LLM auto-configured via OpenRouter")

        logger.info("Orion Backend Ready")

    except Exception as e:
        logger.error(f"Error during startup: {e}")

    yield

    # Shutdown: close DB pool, close Redis
    logger.info("Shutting down Orion FastAPI application...")
    try:
        from orion.core.cleanup import stop_cleanup_task
        if hasattr(app.state, 'cleanup_task'):
            await stop_cleanup_task(app.state.cleanup_task)
        if engine:
            await engine.dispose()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
