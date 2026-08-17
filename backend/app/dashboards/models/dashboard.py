"""Dashboard model â€” stores full dashboard as JSONB blobs (pages, widgets, datasets, settings)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.database import AccountBase as Base


def _utcnow():
    return datetime.now(timezone.utc)


class Dashboard(Base):
    __tablename__ = "dashboards"

    id = Column(String(36), primary_key=True)            # UUID from frontend
    name = Column(Text, nullable=False)
    folder_id = Column(Text, nullable=True)
    is_draft = Column(Boolean, nullable=False, default=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    permission_mode = Column(String(20), nullable=False, default="individual")  # individual | shared
    # Full graph stored as JSONB â€” avoids 10-table join complexity for v1
    pages = Column(JSONB, nullable=False, default=list)
    widgets = Column(JSONB, nullable=False, default=list)
    datasets = Column(JSONB, nullable=False, default=list)
    settings = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
