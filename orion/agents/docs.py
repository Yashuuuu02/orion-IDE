from orion.agents.base import BaseAgent
from orion.schemas.agent import AgentRole

class DocsAgent(BaseAgent):
    role = AgentRole.DOCS
    TOKEN_LIMIT = 20_000
