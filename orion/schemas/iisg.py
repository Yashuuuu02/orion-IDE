from enum import Enum
from typing import Optional
from pydantic import BaseModel

class ClauseType(str, Enum):
    FILE_CREATED = "FILE_CREATED"
    FILE_MODIFIED = "FILE_MODIFIED"
    FILE_DELETED = "FILE_DELETED"
    FUNCTION_EXISTS = "FUNCTION_EXISTS"
    TYPE_SAFE = "TYPE_SAFE"
    TEST_PASSES = "TEST_PASSES"
    NO_REGRESSION = "NO_REGRESSION"
    CUSTOM = "CUSTOM"

class IISGClause(BaseModel):
    clause_id: str
    clause_type: ClauseType
    description: str
    assertion: str
    file_target: Optional[str] = None
    required: bool = True

class IISGContract(BaseModel):
    contract_id: str
    contract_hash: str
    run_id: str
    clauses: list[IISGClause]
    approved_by_user: bool = False
    created_at: float
