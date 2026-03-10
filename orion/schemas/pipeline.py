from enum import Enum

class RunMode(str, Enum):
    PLANNING = "planning"
    FAST = "fast"

class ContextScope(str, Enum):
    CURRENT_FILE = "current_file"
    CODEBASE = "codebase"

class RunPreset(str, Enum):
    THOROUGH = "thorough"
    BALANCED = "balanced"
    LEAN = "lean"
    CUSTOM = "custom"
