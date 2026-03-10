import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from orion.core.config import settings

db_url = settings.DATABASE_URL

engine = create_async_engine(db_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with async_session_maker() as session:
        yield session

async def create_all_tables():
    from orion.models.base import Base
    import orion.models.session
    import orion.models.run
    import orion.models.checkpoint
    import orion.models.iisg
    import orion.models.agent_execution
    import orion.models.validation
    import orion.models.memory
    import orion.models.cost_tracking

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
