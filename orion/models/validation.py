import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class ValidationResultModel(Base):
    __tablename__ = "validation_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False)
    layers = Column(JSON, nullable=False)
    total_duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
