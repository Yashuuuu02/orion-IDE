import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from orion.core.config import settings

from sqlalchemy import event

db_url = settings.DATABASE_URL
connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}

engine = create_async_engine(db_url, echo=False, connect_args=connect_args)

if "sqlite" in db_url:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
AsyncSessionLocal = async_session_maker  # alias used by pipeline components


async def get_db():
    async with async_session_maker() as session:
        yield session

async def create_all_tables():
    from orion.models.base import Base
    import orion.models.session
    import orion.models.run          # includes PipelineRun + WsEventBuffer
    import orion.models.checkpoint
    import orion.models.iisg
    import orion.models.agent_execution
    import orion.models.validation
    import orion.models.memory
    import orion.models.cost_tracking

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
