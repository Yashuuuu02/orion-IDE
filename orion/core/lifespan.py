from contextlib import asynccontextmanager
from fastapi import FastAPI
from orion.core.database import create_all_tables, engine
from orion.core.redis_client import init_redis, close_redis
import logging
from alembic import command
from alembic.config import Config
import asyncio

logger = logging.getLogger(__name__)

def run_upgrade():
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
        await create_all_tables()
        await init_redis()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_upgrade)

        logger.info("Orion Backend Ready")
    except Exception as e:
        logger.error(f"Error during startup: {e}")

    yield

    # Shutdown: close DB pool, close Redis
    logger.info("Shutting down Orion FastAPI application...")
    try:
        await close_redis()
        if engine:
            await engine.dispose()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
