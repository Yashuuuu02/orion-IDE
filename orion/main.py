from fastapi import FastAPI
from orion.core.lifespan import lifespan

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(session_id: str):
    pass

@app.post("/api/v1/pipeline")
async def pipeline():
    return {}

@app.get("/api/v1/settings")
async def get_settings():
    return {}

@app.get("/api/v1/memory")
async def get_memory():
    return {}

@app.get("/api/v1/skills")
async def get_skills():
    return {}
