"""SQLAlchemy models for the Ontology & Knowledge Graph Subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import AccountBase as Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OntologyType(Base):
    """Entity type / Kind definition in the ontology metamodel."""

    __tablename__ = "ontology_types"

    id = Column(String(100), primary_key=True)  # slug e.g. 'project', 'domain', 'capability', 'element'
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    shape = Column(String(50), nullable=False, default="circle")  # 'hexagon', 'chip', 'circle', 'pad'
    base_radius = Column(Integer, nullable=False, default=12)  # px size on canvas
    tier = Column(Integer, nullable=False, default=2)  # 0=root apex, 1=inner ring, 2=mid ring, 3=outer cluster
    color = Column(String(50), nullable=True)
    icon = Column(String(100), nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    outgoing_relations = relationship(
        "OntologyTypeRelation",
        foreign_keys="OntologyTypeRelation.source_type_id",
        back_populates="source_type",
        cascade="all, delete-orphan",
    )
    incoming_relations = relationship(
        "OntologyTypeRelation",
        foreign_keys="OntologyTypeRelation.target_type_id",
        back_populates="target_type",
        cascade="all, delete-orphan",
    )


class OntologyTypeRelation(Base):
    """Allowed relationship rule between two entity types in the ontology metamodel."""

    __tablename__ = "ontology_type_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type_id = Column(String(100), ForeignKey("ontology_types.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(100), nullable=False)  # 'contains', 'depends_on', 'relies_on', 'reads', 'is_similar_to', 'relates'
    target_type_id = Column(String(100), ForeignKey("ontology_types.id", ondelete="CASCADE"), nullable=False)
    is_hierarchical = Column(Boolean, nullable=False, default=False)  # True for parent-child containment (contains)
    is_system = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    source_type = relationship("OntologyType", foreign_keys=[source_type_id], back_populates="outgoing_relations")
    target_type = relationship("OntologyType", foreign_keys=[target_type_id], back_populates="incoming_relations")

    __table_args__ = (
        UniqueConstraint("source_type_id", "relation_type", "target_type_id", name="uq_ontology_type_relation"),
    )


class OntologyGraph(Base):
    """Knowledge Graph instance metadata."""

    __tablename__ = "ontology_graphs"

    id = Column(String(100), primary_key=True)  # e.g. 'default' or UUID
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=True, default="1.0.0")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    raw_yaml = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    nodes = relationship("OntologyNode", back_populates="graph", cascade="all, delete-orphan")
    edges = relationship("OntologyEdge", back_populates="graph", cascade="all, delete-orphan")


class OntologyNode(Base):
    """Knowledge Graph entity instance / node."""

    __tablename__ = "ontology_nodes"

    id = Column(String(255), primary_key=True)  # Node ID / slug e.g. 'domains/topology-navigation'
    graph_id = Column(String(100), ForeignKey("ontology_graphs.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    type_id = Column(String(100), nullable=False)  # matches OntologyType.id (e.g. 'project', 'domain')
    uid = Column(String(100), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(String(255), nullable=True)
    domain_id = Column(String(255), nullable=True)
    path = Column(String(500), nullable=True)
    tags = Column(JSONB, nullable=False, default=list)
    status = Column(String(50), nullable=False, default="active")
    properties = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    graph = relationship("OntologyGraph", back_populates="nodes")


class OntologyEdge(Base):
    """Knowledge Graph relationship instance / edge."""

    __tablename__ = "ontology_edges"

    id = Column(String(255), primary_key=True)
    graph_id = Column(String(100), ForeignKey("ontology_graphs.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    source_id = Column(String(255), nullable=False)
    target_id = Column(String(255), nullable=False)
    relation_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    properties = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    graph = relationship("OntologyGraph", back_populates="edges")
