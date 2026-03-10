from enum import Enum
from pydantic import BaseModel

class ValidationLayer(str, Enum):
    SYNTAX = "SYNTAX"
    TYPE = "TYPE"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    INTEGRATION = "INTEGRATION"
    FORMAL = "FORMAL"

class LayerResult(BaseModel):
    layer: ValidationLayer
    passed: bool
    issues: list[str]
    duration_ms: int

class ValidationResult(BaseModel):
    run_id: str
    passed: bool
    layers: list[LayerResult]
    total_duration_ms: int
