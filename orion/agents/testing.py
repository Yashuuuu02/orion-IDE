from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole

class TestingAgent(BaseAgent):
    role = AgentRole.TESTING
    TOKEN_LIMIT = 40_000
