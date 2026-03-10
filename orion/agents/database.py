from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole

class DatabaseAgent(BaseAgent):
    role = AgentRole.DATABASE
    TOKEN_LIMIT = 30_000
