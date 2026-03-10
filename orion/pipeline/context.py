from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid
import hashlib
import time

from orion.schemas.pipeline import RunMode, ContextScope
from orion.schemas.intent import IntentObject
from orion.schemas.stack import StackLock
from orion.schemas.iisg import IISGContract
from orion.schemas.agent import AgentOutput
from orion.schemas.validation import ValidationResult
from orion.schemas.settings import RunConfig
from orion.schemas.skills import OrionMdContext, SkillConflict

class PipelineContext(BaseModel):
    # Identity
    run_id: str
    session_id: str
    workspace_id: str
    mode: RunMode

    # Input
    raw_prompt: str
    context_scope: ContextScope = ContextScope.CODEBASE

    # Derived determinism fields
    run_id_int: int
    intent_hash: str

    # Timestamps
    started_at: float

    # Component outputs
    intent: Optional[IntentObject] = None
    stack_lock: Optional[StackLock] = None
    iisg: Optional[IISGContract] = None
    blueprint: Optional[dict] = None
    task_dag: Optional[dict] = None
    contexts: Optional[dict] = None
    agent_outputs: list[AgentOutput] = []
    merged: Optional[dict] = None
    validation: Optional[ValidationResult] = None
    checkpoint_id: Optional[str] = None
    execution: Optional[dict] = None

    # Skills & context
    orion_md: Optional[OrionMdContext] = None
    skill_conflicts: list[SkillConflict] = []

    # Cost tracking
    cost_estimate: Optional[float] = None
    cost_actual: float = 0.0
    run_config: RunConfig = Field(default_factory=RunConfig)

    # Control flow
    cancelled: bool = False
    error: Optional[str] = None
    recovery_strategy: Optional[str] = None
    active_provider: Optional[str] = None

    # Permissions
    permission_read: bool = True
    permission_write: bool = True
    permission_execute: bool = False
    permission_browser: bool = False
    permission_mcp: bool = True

    @classmethod
    def create(cls, session_id: str, workspace_id: str, raw_prompt: str, mode: RunMode, run_config: RunConfig = None) -> "PipelineContext":
        if run_config is None:
            run_config = RunConfig()

        raw_prompt_hash = hashlib.sha256(raw_prompt.encode('utf-8')).hexdigest()[:16]
        intent_hash = hashlib.sha256(raw_prompt.encode('utf-8')).hexdigest()

        name_str = f"{session_id}:{raw_prompt_hash}:{workspace_id}"
        run_uuid = uuid.uuid5(uuid.NAMESPACE_URL, name_str)
        run_id_int = int.from_bytes(run_uuid.bytes[:8], 'big')

        return cls(
            run_id=str(run_uuid),
            session_id=session_id,
            workspace_id=workspace_id,
            mode=mode,
            raw_prompt=raw_prompt,
            context_scope=run_config.context_scope,
            run_id_int=run_id_int,
            intent_hash=intent_hash,
            started_at=time.time(),
            run_config=run_config
        )
