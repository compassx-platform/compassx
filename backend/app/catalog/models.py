from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func, Computed, Boolean, cast
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import UUID

from app.database import AccountBase as Base


def _uuid() -> str:
    return str(uuid4())


class CatalogTableType(str, Enum):
    POSTGRES_NATIVE = "postgres_native"
    ICEBERG = "iceberg"



class UnifiedCatalog(Base):
    __tablename__ = "catalog_v2_catalogs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalog_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    connection_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    all_workspaces: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Catalog-level blob storage (all schemas inherit unless they override)
    storage_backend_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    base_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    schemas: Mapped[list["UnifiedCatalogSchema"]] = relationship(back_populates="catalog", cascade="all, delete-orphan")

    connection: Mapped[Optional["DBConnection"]] = relationship(
        primaryjoin="cast(foreign(UnifiedCatalog.connection_id), String) == cast(DBConnection.id, String)",
        viewonly=True,
        uselist=False,
    )


class UnifiedCatalogSchema(Base):
    __tablename__ = "catalog_v2_schemas"
    __table_args__ = (UniqueConstraint("catalog_id", "name", name="uq_catalog_v2_schema_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_catalogs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    catalog: Mapped[UnifiedCatalog] = relationship(back_populates="schemas")
    tables: Mapped[list["UnifiedCatalogTable"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    volumes: Mapped[list["UnifiedCatalogVolume"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    notebooks: Mapped[list["UnifiedCatalogNotebook"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    dashboards: Mapped[list["UnifiedCatalogDashboard"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    tools: Mapped[list["UnifiedCatalogTool"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    connections: Mapped[list["UnifiedCatalogConnection"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    queries: Mapped[list["UnifiedCatalogQuery"]] = relationship(back_populates="schema", cascade="all, delete-orphan")

    # Blob storage association (Iceberg schemas only)
    storage_backend_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # FK resolved via service
    base_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class UnifiedCatalogVolume(Base):
    __tablename__ = "catalog_v2_volumes"
    __table_args__ = (UniqueConstraint("schema_id", "name", name="uq_catalog_v2_volume_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    schema: Mapped[UnifiedCatalogSchema] = relationship(back_populates="volumes")


class UnifiedCatalogVolumeFile(Base):
    """Index of files uploaded to a volume (mirrors what is on blob storage)."""
    __tablename__ = "catalog_v2_volume_files"
    __table_args__ = (UniqueConstraint("volume_id", "file_path", name="uq_catalog_v2_volume_file_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    volume_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_volumes.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)   # relative path within volume
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    volume: Mapped["UnifiedCatalogVolume"] = relationship()


class UnifiedCatalogTable(Base):
    __tablename__ = "catalog_v2_tables"
    __table_args__ = (UniqueConstraint("schema_id", "name", name="uq_catalog_v2_table_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_type: Mapped[CatalogTableType] = mapped_column(
        SqlEnum(CatalogTableType, native_enum=False, validate_strings=True), nullable=False
    )
    connection_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_database: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pg_schema: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pg_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_format: Mapped[str] = mapped_column(String(32), nullable=False, default="parquet")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    read_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    write_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    schema: Mapped[UnifiedCatalogSchema] = relationship(back_populates="tables")
    columns: Mapped[list["UnifiedCatalogColumn"]] = relationship(back_populates="table", cascade="all, delete-orphan")

    connection: Mapped[Optional["DBConnection"]] = relationship(
         primaryjoin="cast(foreign(UnifiedCatalogTable.connection_id), String) == cast(DBConnection.id, String)",
         viewonly=True,
         uselist=False,
     )


class UnifiedCatalogColumn(Base):
    __tablename__ = "catalog_v2_columns"
    __table_args__ = (UniqueConstraint("table_id", "name", name="uq_catalog_v2_column_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    table_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_tables.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(255), nullable=False)
    nullable: Mapped[bool] = mapped_column(nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    table: Mapped[UnifiedCatalogTable] = relationship(back_populates="columns")


class UnifiedCatalogLineage(Base):
    __tablename__ = "catalog_v2_lineage"
    __table_args__ = (
        UniqueConstraint("source_table_id", "target_table_id", name="uq_catalog_v2_lineage_edge"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_table_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_tables.id", ondelete="CASCADE"), nullable=False)
    target_table_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_tables.id", ondelete="CASCADE"), nullable=False)
    transformation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UnifiedCatalogNotebook(Base):
    __tablename__ = "catalog_notebooks"
    __table_args__ = (
        UniqueConstraint("catalog_name", "schema_name", "name", name="uq_catalog_notebooks_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="RESTRICT"), nullable=False)
    catalog_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(
        String(765),
        Computed("catalog_name || '.' || schema_name || '.' || name", persisted=True),
        nullable=False,
    )
    blob_path: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_compute_resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_kernel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)

    schema: Mapped[UnifiedCatalogSchema] = relationship(back_populates="notebooks", lazy="joined")

    @property
    def storage_location(self) -> str:
        # Schema-level override takes priority; fall back to catalog-level
        schema_has_storage = self.schema and self.schema.storage_backend_id
        catalog_has_storage = (
            self.schema
            and hasattr(self.schema, "catalog")
            and self.schema.catalog
            and self.schema.catalog.storage_backend_id
        )
        if schema_has_storage or catalog_has_storage:
            base = (self.schema.base_path if schema_has_storage else None) or f"{self.catalog_name}/{self.schema_name}/"
            return f"{base.rstrip('/')}/notebooks/{self.blob_path}"
        return f"notebooks/{self.blob_path}"


class CatalogWorkspaceBinding(Base):
    __tablename__ = "catalog_v2_workspace_bindings"
    __table_args__ = (
        UniqueConstraint("catalog_id", "workspace_id", name="uq_catalog_workspace_binding"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_catalogs.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    privilege: Mapped[str] = mapped_column(String(50), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bound_by: Mapped[str] = mapped_column(String(255), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UnifiedCatalogDashboard(Base):
    __tablename__ = "catalog_dashboards"
    __table_args__ = (
        UniqueConstraint("catalog_name", "schema_name", "name", name="uq_catalog_dashboards_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="RESTRICT"), nullable=False)
    catalog_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(
        String(765),
        Computed("catalog_name || '.' || schema_name || '.' || name", persisted=True),
        nullable=False,
    )
    dashboard_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)

    schema: Mapped[UnifiedCatalogSchema] = relationship(back_populates="dashboards", lazy="joined")


class UnifiedCatalogTool(Base):
    __tablename__ = "catalog_tools"
    __table_args__ = (
        UniqueConstraint("catalog_name", "schema_name", "name", name="uq_catalog_tools_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="RESTRICT"), nullable=False)
    catalog_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(
        String(765),
        Computed("catalog_name || '.' || schema_name || '.' || name", persisted=True),
        nullable=False,
    )
    source_notebook_object_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    param_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    connection_dependencies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")

    schema: Mapped[UnifiedCatalogSchema] = relationship(back_populates="tools", lazy="joined")
    versions: Mapped[list["UnifiedCatalogToolVersion"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan", order_by="UnifiedCatalogToolVersion.version"
    )


class UnifiedCatalogToolVersion(Base):
    __tablename__ = "catalog_tool_versions"
    __table_args__ = (
        UniqueConstraint("tool_id", "version", name="uq_catalog_tool_versions_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tool_id: Mapped[str] = mapped_column(ForeignKey("catalog_tools.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_notebook_object_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    param_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    connection_dependencies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    promoted_by: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tool: Mapped[UnifiedCatalogTool] = relationship(back_populates="versions")


class UnifiedCatalogConnection(Base):
    """First-class Catalog Connection (SQL Database, REST API, Loki, Prometheus, Custom)."""

    __tablename__ = "catalog_v2_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str | None] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="SET NULL"), nullable=True)
    catalog_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(765), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="database")  # database | api | observability | custom
    connector_type: Mapped[str] = mapped_column(String(100), nullable=False, default="postgres")  # postgres, mysql, mssql, rest_api, loki, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # Unencrypted config (host, port, db, url)
    auth_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet encrypted ciphertext
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")  # active | disabled | error
    owner: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")

    schema: Mapped[UnifiedCatalogSchema | None] = relationship(back_populates="connections", lazy="joined")


class UnifiedCatalogQuery(Base):
    __tablename__ = "catalog_queries"
    __table_args__ = (
        UniqueConstraint("catalog_name", "schema_name", "name", name="uq_catalog_queries_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(ForeignKey("catalog_v2_schemas.id", ondelete="RESTRICT"), nullable=False)
    catalog_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(
        String(765),
        Computed("catalog_name || '.' || schema_name || '.' || name", persisted=True),
        nullable=False,
    )
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)

    schema: Mapped[UnifiedCatalogSchema] = relationship(back_populates="queries", lazy="joined")
    versions: Mapped[list["UnifiedCatalogQueryVersion"]] = relationship(
        back_populates="query", cascade="all, delete-orphan", order_by="UnifiedCatalogQueryVersion.version"
    )


class UnifiedCatalogQueryVersion(Base):
    __tablename__ = "catalog_query_versions"
    __table_args__ = (
        UniqueConstraint("query_id", "version", name="uq_catalog_query_versions_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query_id: Mapped[str] = mapped_column(ForeignKey("catalog_queries.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="default_user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    query: Mapped[UnifiedCatalogQuery] = relationship(back_populates="versions")
