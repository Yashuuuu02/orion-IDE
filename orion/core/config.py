from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# CONSTANTS
EMBEDDING_MODEL: str = "text-embedding-3-small"
SKILL_MATCH_THRESHOLD: float = 0.82
TOP_K_SKILLS: int = 2
FAST_MODE_SINGLE_AGENT_TOKEN_LIMIT: int = 80_000
CIRCUIT_BREAKER_LLM_THRESHOLD: int = 3
CIRCUIT_BREAKER_LLM_WINDOW_SECONDS: int = 60
CIRCUIT_BREAKER_MCP_THRESHOLD: int = 5
CIRCUIT_BREAKER_MCP_WINDOW_SECONDS: int = 60
RETRY_BACKOFF_SEQUENCE: list[float] = [1.0, 2.0, 4.0, 8.0, 16.0]
RETRY_MAX_ATTEMPTS: int = 5
SEED_SUPPORTED_PROVIDERS: frozenset = frozenset({"openai", "groq", "nvidia_nim"})

class Settings(BaseSettings):
    ORION_ENV: str = "local"
    DATABASE_URL: str
    REDIS_URL: str = ""
    WS_PORT: int = 8000
    MOCK_LLM: bool = False
    SKILL_GLOBAL_PATH: str = "~/.orion/skills"
    CHECKPOINT_DIR: str = "~/.orion/checkpoints"
    LOG_LEVEL: str = "INFO"
    MAX_CONCURRENT_RUNS: int = 3
    SESSION_BUDGET_USD: float = 5.0
    DAILY_BUDGET_USD: float = 50.0
    MONTHLY_BUDGET_USD: float = 500.0
    OPENROUTER_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
