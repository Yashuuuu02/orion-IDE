from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from orion.mcp.dispatcher import mcp_dispatcher

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    use_current_file: bool = False
    file_context: Optional[str] = None

@router.post("")
async def run_search(request: SearchRequest, x_orion_session_id: Optional[str] = Header(None, alias="X-Orion-Session-Id")):
    if not x_orion_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Orion-Session-Id header")

    context = request.file_context if request.use_current_file else None
    results = await mcp_dispatcher.search(request.query, context)
    return results
