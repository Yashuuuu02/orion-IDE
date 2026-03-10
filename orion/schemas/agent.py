from enum import Enum
from typing import Optional
from pydantic import BaseModel

class AgentRole(str, Enum):
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    DATABASE = "DATABASE"
    DEVOPS = "DEVOPS"
    TESTING = "TESTING"
    DOCS = "DOCS"

class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class FileChange(BaseModel):
    file_path: str
    operation: str
    content: Optional[str] = None
    diff: Optional[str] = None
    reason: str

class AgentOutput(BaseModel):
    agent_role: AgentRole
    run_id: str
    success: bool
    file_changes: list[FileChange]
    iisg_satisfied: list[str]
    tokens_used: int
    duration_ms: int
    error: Optional[str] = None
