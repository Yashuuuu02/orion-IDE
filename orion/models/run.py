import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("orion_sessions.id"), nullable=False)
    run_id = Column(String, unique=True, nullable=False)
    mode = Column(String, nullable=False)
    raw_prompt = Column(String, nullable=False)
    status = Column(String, nullable=False)
    cost_estimate = Column(Float, nullable=True)
    cost_actual = Column(Float, default=0.0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error = Column(String, nullable=True)
