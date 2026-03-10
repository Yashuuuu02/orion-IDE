from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole

class FrontendAgent(BaseAgent):
    role = AgentRole.FRONTEND
    TOKEN_LIMIT = 50_000
