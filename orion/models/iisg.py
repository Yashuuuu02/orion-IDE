import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from orion.models.base import Base

class IISGContractModel(Base):
    __tablename__ = "iisg_contracts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, nullable=False)
    contract_hash = Column(String, nullable=False)
    clauses = Column(JSON, nullable=False)
    approved_by_user = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
