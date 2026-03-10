import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, nullable=False)
    agent_role = Column(String, nullable=False)
    success = Column(Boolean, nullable=False)
    tokens_used = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)
    file_changes = Column(JSON, nullable=False)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
