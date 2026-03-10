import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class CostTracking(Base):
    __tablename__ = "cost_tracking"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    provider = Column(String, nullable=False)
    tokens_in = Column(Integer, nullable=False)
    tokens_out = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
