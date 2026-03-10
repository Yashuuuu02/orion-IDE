from pydantic import BaseModel, ConfigDict

class StackLock(BaseModel):
    model_config = ConfigDict(frozen=True)
    lock_hash: str
    language: str
    framework: str
    test_runner: str
    package_manager: str
    dependencies: dict[str, str]
    workspace_root: str
    locked_at: float
    provider_supports_seed: bool = True  # False for Anthropic/Ollama
