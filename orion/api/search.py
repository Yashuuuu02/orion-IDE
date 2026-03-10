from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from orion.mcp.dispatcher import mcp_dispatcher
from orion.core.dependencies import require_session_id

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    use_current_file: bool = False
    file_context: Optional[str] = None

@router.post("")
async def run_search(request: SearchRequest, session_id: str = Depends(require_session_id)):
    context = request.file_context if request.use_current_file else None
    results = await mcp_dispatcher.search(request.query, context)
    return results
