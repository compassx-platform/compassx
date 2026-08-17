from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base


def utcnow():
    return datetime.now(timezone.utc)


class EntityWorkflow(Base):
    __tablename__ = "entity_workflows"

    entity_name = Column(Text, ForeignKey("entity_definitions.name", ondelete="CASCADE"), primary_key=True)
    initial_state = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, server_default="true", default=True)

    states = relationship(
        "EntityState",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    transitions = relationship(
        "EntityTransition",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EntityState(Base):
    __tablename__ = "entity_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_name = Column(Text, ForeignKey("entity_workflows.entity_name", ondelete="CASCADE"), nullable=False)
    state_name = Column(Text, nullable=False)
    is_terminal = Column(Boolean, nullable=False, server_default="false", default=False)

    workflow = relationship("EntityWorkflow", back_populates="states")


class EntityTransition(Base):
    __tablename__ = "entity_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_name = Column(Text, ForeignKey("entity_workflows.entity_name", ondelete="CASCADE"), nullable=False)
    from_state = Column(Text, nullable=False)
    to_state = Column(Text, nullable=False)

    workflow = relationship("EntityWorkflow", back_populates="transitions")


class EntityStateLog(Base):
    __tablename__ = "entity_state_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_name = Column(Text, ForeignKey("entity_definitions.name", ondelete="CASCADE"), nullable=False)
    record_id = Column(Integer, ForeignKey("entity_records.id", ondelete="CASCADE"), nullable=False)
    from_state = Column(Text, nullable=True)
    to_state = Column(Text, nullable=False)
    changed_by = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
