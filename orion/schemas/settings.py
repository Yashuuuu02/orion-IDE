from typing import Optional
from pydantic import BaseModel
from orion.schemas.pipeline import RunPreset, ContextScope, RunMode
from orion.schemas.agent import AgentRole

class ProviderConfig(BaseModel):
    provider: str
    model_planning: str
    model_fast: str
    api_key: str  # held in memory only, never written to disk
    base_url: Optional[str] = None
    enabled: bool = True

class AgentRunConfig(BaseModel):
    role: AgentRole
    enabled: bool = True
    token_limit: int

class RunConfig(BaseModel):
    preset: RunPreset = RunPreset.BALANCED
    agent_configs: list[AgentRunConfig] = []
    cost_cap_usd: Optional[float] = None
    context_scope: ContextScope = ContextScope.CODEBASE

    def get_token_limit(self, role: AgentRole) -> int:
        for config in self.agent_configs:
            if config.role == role:
                return config.token_limit
        return 0

    def is_agent_enabled(self, role: AgentRole) -> bool:
        for config in self.agent_configs:
            if config.role == role:
                return config.enabled
        return False

class OrionSettings(BaseModel):
    providers: list[ProviderConfig] = []
    active_provider: Optional[str] = None
    default_run_config: RunConfig = RunConfig()
    default_mode: RunMode = RunMode.PLANNING  # Planning Mode is always the session default
    budget_session_usd: float = 5.0
    budget_session_alert_usd: float = 4.0
    budget_daily_usd: float = 50.0
    budget_daily_alert_usd: float = 40.0
    budget_monthly_usd: float = 500.0
    budget_monthly_alert_usd: float = 400.0
