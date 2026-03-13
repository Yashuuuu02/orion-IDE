from fastapi import Header, HTTPException
from orion.core.database import async_session_maker


async def require_session_id(
    x_orion_session_id: str = Header(None)
) -> str:
    if not x_orion_session_id:
        raise HTTPException(status_code=400, detail="X-Orion-Session-Id header required")
    return x_orion_session_id

async def get_db():
    async with async_session_maker() as session:
        yield session


