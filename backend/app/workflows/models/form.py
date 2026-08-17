from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB

from app.database import SystemBase as Base


def utcnow():
    return datetime.now(timezone.utc)


class Form(Base):
    __tablename__ = "forms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    form_id = Column(Text, unique=True, nullable=False)
    entity_name = Column(String, nullable=False)
    schema = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)