from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Boolean, Text, DateTime, ForeignKey, Index, Integer,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base


def utcnow():
    return datetime.now(timezone.utc)


class EntityDefinition(Base):
    __tablename__ = "entity_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)
    entity_type = Column(String(50), nullable=False, server_default="generic")
    asset_scoped = Column(Boolean, default=True)
    time_based = Column(Boolean, default=False)
    # Kept for backward compat; maps to time_based going forward
    time_series = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    fields = relationship("EntityField", back_populates="entity", cascade="all, delete-orphan")


class EntityField(Base):
    __tablename__ = "entity_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entity_definitions.id"), nullable=False)
    field_name = Column(Text, nullable=False)
    field_type = Column(Text, nullable=False)  # canonical: string, text, number, boolean, datetime, json

    # Validation / indexing intent
    is_required = Column(Boolean, default=False)
    is_indexed = Column(Boolean, default=False)  # stored for future projection indexing

    # Source tracking
    # "entity" = defined at entity-creation time by admin
    # "form"   = added via form builder and synced back to entity
    field_source = Column(String(20), nullable=False, server_default="entity")

    # System field support
    is_system = Column(Boolean, default=False)
    # When True: value is ALWAYS overridden by server (e.g. __now__, __uuid__)
    # When False + is_system True: injected only if caller did not supply it
    system_generated = Column(Boolean, default=False)
    default_value = Column(Text, nullable=True)  # supports special tokens: __now__, __uuid__

    metadata_ = Column("metadata", JSONB, default=dict)

    entity = relationship("EntityDefinition", back_populates="fields")


class EntityRecord(Base):
    __tablename__ = "entity_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, nullable=False)
    asset_id = Column(String, nullable=True)   # nullable for non-asset-scoped entities
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    organization_id = Column(String, nullable=True)
    status = Column(String, default="OPEN")
    data_json = Column(JSONB, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_entity_asset_time", "entity_id", "asset_id", "timestamp"),
        Index("idx_entity_json", "data_json", postgresql_using="gin"),
    )