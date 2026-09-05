"""Pydantic schemas for Ontology Metamodel and Knowledge Graph validation & APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


NodeShape = Literal["hexagon", "chip", "circle", "pad"]


# ─── Entity Type Schemas ────────────────────────────────────────────────────────

class TypeDefinitionBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=200, description="Display name of the type")
    description: Optional[str] = Field(None, description="Detailed explanation of the entity type")
    shape: NodeShape = Field("circle", description="Visual shape: hexagon, chip, circle, or pad")
    base_radius: int = Field(12, ge=5, le=80, description="Canvas base radius in pixels")
    tier: int = Field(2, ge=0, le=5, description="Hierarchy tier: 0=root apex, 1=inner, 2=mid, 3=outer")
    color: Optional[str] = Field(None, description="Optional custom accent color")
    icon: Optional[str] = Field(None, description="Optional Lucide icon name")


class TypeDefinitionCreate(TypeDefinitionBase):
    id: str = Field(..., min_length=1, max_length=100, description="Unique slug ID (e.g. 'microservice')")


class TypeDefinitionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    shape: Optional[NodeShape] = None
    base_radius: Optional[int] = Field(None, ge=5, le=80)
    tier: Optional[int] = Field(None, ge=0, le=5)
    color: Optional[str] = None
    icon: Optional[str] = None


class TypeDefinitionResponse(TypeDefinitionBase):
    id: str
    is_system: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Type Relationship Schemas (Metamodel) ──────────────────────────────────────

class TypeRelationBase(BaseModel):
    source_type_id: str = Field(..., description="Source entity type ID")
    relation_type: str = Field(..., min_length=1, max_length=100, description="Relation slug e.g. 'contains', 'depends_on'")
    target_type_id: str = Field(..., description="Target entity type ID")
    is_hierarchical: bool = Field(False, description="True for parent-child tree hierarchy (e.g. contains)")
    is_system: bool = Field(False, description="True for protected system relation rules")
    description: Optional[str] = Field(None, description="Explanation of allowed relationship")


class TypeRelationCreate(TypeRelationBase):
    pass


class TypeRelationResponse(TypeRelationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Graph Instance Schemas ─────────────────────────────────────────────────────

class GraphNodeInstance(BaseModel):
    id: str
    kind: str = Field(..., description="Must match a registered TypeDefinition ID")
    uid: Optional[str] = None
    title: str
    description: Optional[str] = None
    parentId: Optional[str] = Field(None, alias="parent_id")
    domainId: Optional[str] = Field(None, alias="domain_id")
    path: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = "active"
    properties: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class GraphEdgeInstance(BaseModel):
    id: str
    source: str = Field(..., alias="source_id")
    target: str = Field(..., alias="target_id")
    type: str = Field(..., alias="relation_type")
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class KnowledgeGraphDataset(BaseModel):
    id: Optional[str] = "default"
    name: str = "CompassX & Ontology Atlas"
    version: Optional[str] = "1.0.0"
    description: Optional[str] = None
    yaml_content: Optional[str] = None
    nodes: List[GraphNodeInstance] = Field(default_factory=list)
    edges: List[GraphEdgeInstance] = Field(default_factory=list)


# ─── Validation & Ingestion Schemas ─────────────────────────────────────────────

class GraphValidationRequest(BaseModel):
    yaml_content: Optional[str] = None
    dataset: Optional[KnowledgeGraphDataset] = None


class GraphValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


class KnowledgeGraphImportRequest(BaseModel):
    yaml_content: Optional[str] = None
    dataset: Optional[KnowledgeGraphDataset] = None
    graph_id: str = "default"
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None


class GraphNodeCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=200, description="Unique slug ID")
    kind: str = Field(..., description="Entity type ID (e.g. 'domain', 'capability', 'element')")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    parentId: Optional[str] = Field(None, alias="parent_id")
    domainId: Optional[str] = Field(None, alias="domain_id")
    path: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = "active"
    properties: Dict[str, Any] = Field(default_factory=dict)
    graph_id: str = "default"

    class Config:
        populate_by_name = True


class GraphNodeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    kind: Optional[str] = None
    description: Optional[str] = None
    parentId: Optional[str] = Field(None, alias="parent_id")
    domainId: Optional[str] = Field(None, alias="domain_id")
    path: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class GraphEdgeCreate(BaseModel):
    id: Optional[str] = None
    source: str = Field(..., alias="source_id")
    target: str = Field(..., alias="target_id")
    type: str = Field(..., alias="relation_type")
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    graph_id: str = "default"

    class Config:
        populate_by_name = True
