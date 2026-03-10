from typing import Any
from pydantic import BaseModel

class CheckpointSnapshot(BaseModel):
    checkpoint_id: str
    run_id: str
    session_id: str
    files_snapshot: dict[str, str]  # path -> content
    created_at: float
    pipeline_state: dict[str, Any]

class RollbackRequest(BaseModel):
    run_id: str
    checkpoint_id: str
    reason: str
