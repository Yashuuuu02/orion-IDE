from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole

class DevOpsAgent(BaseAgent):
    role = AgentRole.DEVOPS
    TOKEN_LIMIT = 30_000
