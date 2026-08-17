"""Pydantic schemas for Data Catalog API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Connection CRUD ──────────────────────────────────────────────────────────

class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    default_database: str = Field(default="postgres", max_length=255)


class ConnectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    host: str | None = Field(None, min_length=1, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = None
    default_database: str | None = Field(None, max_length=255)


class ConnectionResponse(BaseModel):
    """Password is intentionally excluded from all API responses."""
    id: int
    name: str
    host: str
    port: int
    username: str
    default_database: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectionTestRequest(BaseModel):
    host: str = Field(..., min_length=1)
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    database: str = Field(default="postgres")


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    server_version: str | None = None


# ── Catalog browsing ─────────────────────────────────────────────────────────

class DatabaseItem(BaseModel):
    name: str
    owner: str | None = None


class DatabaseListResponse(BaseModel):
    databases: list[DatabaseItem]


class SchemaItem(BaseModel):
    name: str
    owner: str | None = None


class SchemaListResponse(BaseModel):
    schemas: list[SchemaItem]


class TableItem(BaseModel):
    name: str
    schema_name: str
    table_type: str  # "BASE TABLE" | "VIEW"
    row_estimate: int | None = None


class TableListResponse(BaseModel):
    tables: list[TableItem]


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    is_nullable: bool
    column_default: str | None = None
    ordinal_position: int
    character_maximum_length: int | None = None


class TablePreviewResponse(BaseModel):
    columns: list[ColumnInfo]
    rows: list[dict[str, Any]]
    total_rows: int
    truncated: bool


# ── SQL execution ─────────────────────────────────────────────────────────────

class SqlExecuteRequest(BaseModel):
    connection_id: int
    database: str
    sql: str = Field(..., min_length=1)
    limit: int = Field(default=1000, ge=1, le=5000)


class SqlExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool
    error: str | None = None