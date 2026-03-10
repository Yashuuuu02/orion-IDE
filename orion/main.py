from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from orion.core.lifespan import lifespan
from orion.api.health import router as health_router
from orion.api.router import api_v1_router
from orion.api.ws import ws_manager

app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
app.include_router(api_v1_router)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.handle_message(session_id, data, websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
