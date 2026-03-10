import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, ForeignKey("pipeline_runs.run_id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    files_snapshot = Column(JSON, nullable=False)
    pipeline_state = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
