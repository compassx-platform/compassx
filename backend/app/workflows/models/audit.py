from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB

from app.database import SystemBase as Base


def utcnow():
    return datetime.now(timezone.utc)


class EntityAuditLog(Base):
    __tablename__ = "entity_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_record_id = Column(Integer, ForeignKey("entity_records.id"), nullable=True)
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)
    changed_by = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), default=utcnow)