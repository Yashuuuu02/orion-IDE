from enum import Enum
from pydantic import BaseModel

class IntentType(str, Enum):
    FEATURE = "FEATURE"
    REFACTOR = "REFACTOR"
    BUG_FIX = "BUG_FIX"
    SCHEMA_CHANGE = "SCHEMA_CHANGE"
    QUESTION = "QUESTION"
    OTHER = "OTHER"

class IntentObject(BaseModel):
    intent_hash: str
    intent_type: IntentType
    summary: str
    affected_files: list[str] = []
    affected_roles: list[str] = []
    complexity: int  # 1-5
    requires_iisg: bool
    raw_prompt: str
