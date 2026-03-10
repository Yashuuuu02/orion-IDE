import pytest
from httpx import AsyncClient, ASGITransport
from orion.main import app

@pytest.mark.asyncio
async def test_health_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_health_detailed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/detailed")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "db" in data
    assert "redis" in data
    assert "llm_configured" in data
