from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.catalog.models import CatalogTableType





class RemoteDatabaseRead(BaseModel):
    name: str
    owner: str | None = None


class RemoteSchemaRead(BaseModel):
    name: str
    owner: str | None = None


class RemoteTableRead(BaseModel):
    name: str
    schema_name: str
    table_type: str
    row_estimate: int | None = None


class CatalogColumnRead(BaseModel):
    name: str
    data_type: str
    nullable: bool
    description: str | None = None
    ordinal: int
    properties: dict[str, Any] = Field(default_factory=dict)



class CatalogTableRead(BaseModel):
    id: str
    fqn: str
    catalog: str
    schema_name: str
    name: str
    table_type: CatalogTableType
    description: str | None
    owner: str
    read_roles: list[str]
    write_roles: list[str]
    properties: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    connection_id: int | None = None
    connection_name: str | None = None
    source_database: str | None = None
    pg_schema: str | None = None
    pg_table: str | None = None
    metadata_location: str | None = None
    storage_location: str | None = None
    columns: list[CatalogColumnRead] = Field(default_factory=list)


class TableCreate(BaseModel):
    name: str
    description: str | None = None
    table_type: str = "iceberg"


class VolumeCreate(BaseModel):
    name: str
    description: str | None = None


class VolumeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    schema_id: str
    name: str
    description: str | None = None
    storage_location: str | None = None
    owner: str
    created_by: str
    created_at: datetime


class SchemaCreate(BaseModel):
    name: str
    description: str | None = None


class SchemaRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    catalog_id: str
    name: str
    description: str | None = None
    created_by: str
    created_at: datetime


class CatalogCreate(BaseModel):
    name: str
    description: str | None = None
    catalog_type: str | None = None  # "postgres" or "iceberg"
    connection_id: int | None = None
    database_name: str | None = None
    storage_backend_id: str | None = None
    base_path: str | None = None


class CatalogRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    description: str | None = None
    catalog_type: str | None = None
    connection_id: int | None = None
    database_name: str | None = None
    storage_backend_id: str | None = None
    base_path: str | None = None
    created_by: str
    created_at: datetime


class CatalogSchemaSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    table_count: int = 0


class CatalogSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    catalog_type: str | None = None
    connection_id: int | None = None
    database_name: str | None = None
    schema_count: int = 0
    table_count: int = 0
    schemas: list[CatalogSchemaSummary] = Field(default_factory=list)


class SampleDataRead(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int


class LineageEdgeCreate(BaseModel):
    source_fqn: str
    target_fqn: str
    transformation: str | None = None


class LineageEdgeRead(BaseModel):
    source_fqn: str
    target_fqn: str
    transformation: str | None = None
    created_at: datetime | None = None


class LineageGraphRead(BaseModel):
    upstream: list[LineageEdgeRead] = Field(default_factory=list)
    downstream: list[LineageEdgeRead] = Field(default_factory=list)


class DataSourceProfileRead(BaseModel):
    """AI-inferred profiling data for a table, produced by the Layer-1 Profiler agent."""

    id: int
    connection_id: int | None = None
    target_type: str | None = None
    catalog_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    row_count: int | None = None
    last_profiled_at: datetime | None = None
    profiled_by_agent_run_id: int | None = None
    detected_layer: str | None = None
    columns: list[Any] = Field(default_factory=list)
    candidate_relationships: list[Any] = Field(default_factory=list)
    prior_art_references: list[Any] = Field(default_factory=list)
    unresolved_ambiguities: list[Any] = Field(default_factory=list)
    domain_inference: dict[str, Any] = Field(default_factory=dict)
    timeseries_profile: dict[str, Any] = Field(default_factory=dict)


class NotebookCreate(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_]+$")
    comment: str | None = None
    initial_content: dict[str, Any] | None = None


class NotebookRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    catalog_name: str
    schema_name: str
    name: str
    full_name: str
    blob_path: str
    storage_location: str | None = None
    owner: str
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class NotebookUpdate(BaseModel):
    name: str | None = Field(None, pattern=r"^[a-zA-Z0-9_]+$")
    comment: str | None = None
    owner: str | None = None


class NotebookMove(BaseModel):
    target_catalog: str
    target_schema: str
    new_name: str | None = Field(None, pattern=r"^[a-zA-Z0-9_]+$")


class DashboardCreate(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_]+$")
    comment: str | None = None


class DashboardRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    catalog_name: str
    schema_name: str
    name: str
    full_name: str
    dashboard_id: str | None = None
    owner: str
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class DashboardUpdate(BaseModel):
    name: str | None = Field(None, pattern=r"^[a-zA-Z0-9_]+$")
    comment: str | None = None
    owner: str | None = None


class DashboardMove(BaseModel):
    target_catalog: str
    target_schema: str
    new_name: str | None = Field(None, pattern=r"^[a-zA-Z0-9_]+$")



# ── Workspace-Catalog Bindings ──────────────────────────────────────────────

from enum import Enum

class CatalogPrivilege(str, Enum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"


class BindingCreate(BaseModel):
    catalog_name: str
    privilege: CatalogPrivilege
    is_default: bool = False


class WorkspaceBindingRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    catalog_id: str
    workspace_id: str
    workspace_name: str | None = None
    workspace_slug: str | None = None
    privilege: CatalogPrivilege
    is_default: bool
    bound_by: str
    bound_at: datetime


class VolumeResolveRequest(BaseModel):
    """Request to resolve volume access credentials for notebook kernel."""
    catalog: str
    schema_name: str
    volume: str
    mode: str = "read"  # "read", "write", or "readwrite"
    path: str | None = None  # Optional, used for prefix validation


class VolumeResolveResponse(BaseModel):
    """Response with scoped credentials for volume access."""
    backend_type: str  # "azure" | "s3" | "minio"
    container: str  # Container/bucket name
    prefix: str  # Prefix these credentials are scoped to
    scoped_credential: dict  # Backend-specific credential data
    expires_at: str  # ISO8601 timestamp
    mode: str  # Echo back requested mode

