from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole
from orion.core.config import FAST_MODE_SINGLE_AGENT_TOKEN_LIMIT

class SingleAgent(BaseAgent):
    role = AgentRole.BACKEND  # default, overridden by intent or runner context
    TOKEN_LIMIT = FAST_MODE_SINGLE_AGENT_TOKEN_LIMIT
