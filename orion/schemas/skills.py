from enum import Enum
from typing import Optional
from pydantic import BaseModel

class SkillRecord(BaseModel):
    skill_id: str
    name: str
    description: str
    instructions: list[str]
    source: str  # "global" or "project"
    enabled: bool = True
    path: str = ""

class ConflictSeverity(str, Enum):
    HARD = "hard"
    SOFT = "soft"

class SkillConflict(BaseModel):
    skill_id: str
    skill_name: str
    skill_instruction: str
    conflicting_clause_id: str
    iisg_instruction: str
    severity: ConflictSeverity
    resolution: str = "iisg_wins"

class SkillMatch(BaseModel):
    skill_id: str
    skill_name: str
    score: float
    instructions: list[str]

class OrionMdContext(BaseModel):
    global_path: str
    project_path: str
    global_loaded: bool
    project_loaded: bool
    merged_content: str
