import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class SessionModel(Base):
    __tablename__ = "orion_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    active_provider = Column(String, nullable=True)
    tab_state = Column(JSON, nullable=False)
    permissions = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
