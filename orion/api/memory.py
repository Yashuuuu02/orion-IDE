from fastapi import APIRouter
from pydantic import BaseModel
import uuid

router = APIRouter()

class MemoryEntry(BaseModel):
    content: str

# Simple in-memory dict for the stub so tests can pass without a real DB
_memories = {}

@router.get("/memory")
async def list_memories():
    return list(_memories.values())

@router.post("/memory")
async def add_memory(entry: MemoryEntry):
    mem_id = str(uuid.uuid4())
    mem = {"id": mem_id, "content": entry.content}
    _memories[mem_id] = mem
    return mem

@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    if memory_id in _memories:
        del _memories[memory_id]
        return {"status": "deleted"}
    return {"status": "not_found"}
