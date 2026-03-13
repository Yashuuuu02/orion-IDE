import os
import json
import httpx
import logging
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from pathlib import Path
from orion.core.config import settings

router = APIRouter(prefix="/api/agent")
logger = logging.getLogger(__name__)

MODEL_MAP = {
    "gemini-pro": "google/gemini-2.0-flash-001",
    "claude-sonnet": "anthropic/claude-sonnet-4-5",
    "gpt-4o": "openai/gpt-4o"
}

@router.post("/chat")
async def chat_completion(
    messages: List[Dict[str, str]] = Body(..., embed=True),
    model: str = Body(..., embed=True)
):
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    target_model = MODEL_MAP.get(model, model)
    
    async def event_generator():
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": "http://localhost:8321",
            "X-Title": "Orion IDE",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True
        }

        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                ) as response:
                    if response.status_code != 200:
                        error_detail = await response.aread()
                        logger.error(f"OpenRouter error: {error_detail.decode()}")
                        yield f"data: {json.dumps({'error': 'Failed to connect to OpenRouter'})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        if line.startswith("data: "):
                            yield f"{line}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/file")
async def get_file(path: str = Query(...)):
    full_path = Path(path).expanduser().resolve()
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    try:
        content = full_path.read_text(encoding='utf-8')
        return {"path": str(full_path), "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file")
async def write_file(
    path: str = Body(..., embed=True),
    content: str = Body(..., embed=True)
):
    full_path = Path(path).expanduser().resolve()
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        return {"status": "success", "path": str(full_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/file")
async def delete_file(path: str = Query(...)):
    full_path = Path(path).expanduser().resolve()
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        if full_path.is_file():
            full_path.unlink()
        elif full_path.is_dir():
            import shutil
            shutil.rmtree(full_path)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
async def list_files(dir: str = Query(...)):
    full_path = Path(dir).expanduser().resolve()
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not full_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    try:
        entries = []
        for item in full_path.iterdir():
            entries.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0
            })
        return {"dir": str(full_path), "entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
