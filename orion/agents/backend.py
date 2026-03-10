from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole

class BackendAgent(BaseAgent):
    role = AgentRole.BACKEND
    TOKEN_LIMIT = 50_000
