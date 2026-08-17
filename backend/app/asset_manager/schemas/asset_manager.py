"""Pydantic v2 schemas for the Asset Manager module."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.asset_manager.models.asset_manager import (
    AssetCategory,
    AssetStatus,
    DocumentType,
    EventSeverity,
    MetadataFieldType,
    RelationshipDirection,
)


# â”€â”€ Metadata Schema â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class FieldValidation(BaseModel):
    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    message: str | None = None


class MetadataField(BaseModel):
    key: str
    label: str
    type: MetadataFieldType
    required: bool = False
    default: Any | None = None
    unit: str | None = None
    enum_values: list[str] | None = None
    validation: FieldValidation | None = None
    group: str | None = None
    order: int = 0
    is_searchable: bool = False
    is_filterable: bool = False
    tooltip: str | None = None


class MetadataSchema(BaseModel):
    version: int = 1
    fields: list[MetadataField] = []


# â”€â”€ Asset Type â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetTypeTagCreate(BaseModel):
    id: int | None = None
    tag_key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    name: str = Field(..., min_length=1)
    description: str | None = None
    parameter: str | None = None
    unit: str | None = None
    is_required: bool = False


class AssetTypeTagResponse(BaseModel):
    id: int
    asset_type_id: int
    tag_key: str
    name: str
    description: str | None
    parameter: str | None
    unit: str | None
    is_required: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetTypeTagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parameter: str | None = None
    unit: str | None = None
    is_required: bool | None = None


class AssetTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=200, pattern=r"^[a-z0-9\-]+$")
    category: AssetCategory
    description: str | None = None
    industry_tags: list[str] = []
    icon: str | None = None
    allowed_parents: list[int] = []
    allowed_children: list[int] = []
    metadata_schema: MetadataSchema = Field(default_factory=MetadataSchema)
    is_root: bool = False
    is_leaf: bool = False
    tag_definitions: list[AssetTypeTagCreate] = []


class AssetTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    industry_tags: list[str] | None = None
    icon: str | None = None
    allowed_parents: list[int] | None = None
    allowed_children: list[int] | None = None
    is_root: bool | None = None
    is_leaf: bool | None = None
    tag_definitions: list[AssetTypeTagCreate] | None = None


class AssetTypeResponse(BaseModel):
    id: int
    name: str
    slug: str
    category: AssetCategory
    description: str | None
    industry_tags: list[str]
    icon: str | None
    allowed_parents: list[int]
    allowed_children: list[int]
    metadata_schema: dict[str, Any]
    is_root: bool
    is_leaf: bool
    schema_version: int
    is_deleted: bool = False
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    tag_definitions: list[AssetTypeTagResponse] = []

    model_config = {"from_attributes": True}


class AssetTypeListResponse(BaseModel):
    id: int
    name: str
    slug: str
    category: AssetCategory
    description: str | None
    industry_tags: list[str]
    icon: str | None
    allowed_parents: list[int]
    allowed_children: list[int]
    is_root: bool
    is_leaf: bool
    schema_version: int
    is_deleted: bool = False
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


# â”€â”€ Asset Instance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetInstanceCreate(BaseModel):
    asset_type_id: int
    parent_id: int | None = None
    name: str = Field(..., min_length=1, max_length=500)
    code: str | None = None
    description: str | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    address: str | None = None
    commissioned_at: datetime | None = None
    metadata: dict[str, Any] = {}


class AssetInstanceUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    address: str | None = None
    commissioned_at: datetime | None = None
    decommissioned_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    change_summary: str | None = None


class AssetStatusUpdate(BaseModel):
    status: AssetStatus
    change_summary: str | None = None


class AssetParentUpdate(BaseModel):
    parent_id: int | None = None
    change_summary: str | None = None


class AssetInstanceResponse(BaseModel):
    id: int
    asset_type_id: int
    asset_type_name: str | None = None
    asset_type_slug: str | None = None
    parent_id: int | None
    name: str
    code: str | None
    description: str | None
    status: AssetStatus
    latitude: float | None
    longitude: float | None
    altitude: float | None
    address: str | None
    commissioned_at: datetime | None
    decommissioned_at: datetime | None
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata", default={})
    metadata_schema_version: int
    path: str
    depth: int
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AssetInstanceListResponse(BaseModel):
    id: int
    asset_type_id: int
    asset_type_name: str | None = None
    asset_type_slug: str | None = None
    parent_id: int | None
    name: str
    code: str | None
    status: AssetStatus
    path: str
    depth: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAssets(BaseModel):
    data: list[AssetInstanceListResponse]
    pagination: dict[str, Any]


# â”€â”€ Asset Version â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetVersionResponse(BaseModel):
    id: int
    asset_id: int
    version: int
    snapshot: dict[str, Any]
    change_summary: str | None
    changed_by: str | None
    changed_at: datetime

    model_config = {"from_attributes": True}


# â”€â”€ Asset Relationship â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetRelationshipCreate(BaseModel):
    from_asset_id: int
    to_asset_id: int
    type: str = Field(..., min_length=1, max_length=100)
    direction: RelationshipDirection = RelationshipDirection.UNIDIRECTIONAL
    metadata: dict[str, Any] | None = None
    description: str | None = None


class AssetRelationshipResponse(BaseModel):
    id: int
    from_asset_id: int
    to_asset_id: int
    type: str
    direction: RelationshipDirection
    metadata: dict[str, Any] | None = Field(None, validation_alias="extra_metadata")
    description: str | None
    created_at: datetime
    created_by: str | None

    model_config = {"from_attributes": True, "populate_by_name": True}


# â”€â”€ Asset Event â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetEventCreate(BaseModel):
    asset_id: int
    linked_assets: list[int] = []
    event_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1)
    description: str | None = None
    severity: EventSeverity | None = None
    started_at: datetime
    ended_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    source: str | None = None
    external_ref: str | None = None


class AssetEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: EventSeverity | None = None
    ended_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class AssetEventResponse(BaseModel):
    id: int
    asset_id: int
    linked_assets: list[int]
    event_type: str
    title: str
    description: str | None
    severity: EventSeverity | None
    started_at: datetime
    ended_at: datetime | None
    metadata: dict[str, Any] | None = Field(None, validation_alias="extra_metadata")
    source: str | None
    external_ref: str | None
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Asset Tag ─────────────────────────────────────────────────────────────────

class AssetTagCreate(BaseModel):
    asset_id: int
    tag_id: str = Field(..., min_length=1)
    tag_name: str = Field(..., min_length=1)
    parameter: str | None = None
    unit: str | None = None
    source: str | None = None
    is_primary: bool = False
    asset_type_tag_id: int | None = None


class AssetTagResponse(BaseModel):
    id: int
    asset_id: int
    tag_id: str
    tag_name: str
    parameter: str | None
    unit: str | None
    source: str | None
    is_primary: bool
    created_at: datetime
    asset_type_tag_id: int | None = None
    asset_type_tag: AssetTypeTagResponse | None = None

    model_config = {"from_attributes": True}


# ────────────────────────────────────────────────────────────────────────────────────────

class AssetDocumentCreate(BaseModel):
    asset_id: int
    title: str = Field(..., min_length=1)
    type: DocumentType = DocumentType.OTHER
    url: str = Field(..., min_length=1)
    mime_type: str | None = None
    file_size: int | None = None
    version: str | None = None


class AssetDocumentResponse(BaseModel):
    id: int
    asset_id: int
    title: str
    type: DocumentType
    url: str
    mime_type: str | None
    file_size: int | None
    version: str | None
    uploaded_at: datetime
    uploaded_by: str | None

    model_config = {"from_attributes": True}


# â”€â”€ Hierarchy â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class HierarchyNode(BaseModel):
    id: int
    name: str
    code: str | None
    status: AssetStatus
    asset_type_id: int
    asset_type_name: str | None = None
    asset_type_slug: str | None = None
    icon: str | None = None
    path: str
    depth: int
    has_children: bool = False
    children: list[HierarchyNode] | None = None

    model_config = {"from_attributes": True}


HierarchyNode.model_rebuild()
