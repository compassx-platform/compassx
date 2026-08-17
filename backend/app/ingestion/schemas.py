"""
Pydantic request/response schemas for the Ingestion module.

SECURITY: secret_ref and raw secret values are NEVER returned in responses.
auth_config in responses only contains non-secret metadata (header name,
query param name, username) — never the resolved credential value.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# ── Auth types ────────────────────────────────────────────────────────────────

AUTH_TYPES = ("none", "api_key_header", "api_key_query", "bearer_token", "basic_auth")
PAGINATION_TYPES = ("none", "offset", "page", "cursor_field")
PARAM_SOURCE_TYPES = ("static", "catalog_query", "parent_api")
HTTP_METHODS = ("GET", "POST")


# ── Connection schemas ────────────────────────────────────────────────────────

class ConnectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    base_url: str
    auth_type: str = "none"
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    secret_value: Optional[str] = None   # write-only; encrypted at rest; never returned
    default_headers: Dict[str, Any] = Field(default_factory=dict)
    rate_limit_rps: float = 5.0
    max_concurrency: int = 5


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    default_headers: Optional[Dict[str, Any]] = None
    rate_limit_rps: Optional[float] = None
    max_concurrency: Optional[int] = None


class ConnectionRotateSecret(BaseModel):
    new_secret_value: str


class ConnectionOut(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: Optional[str]
    base_url: str
    auth_type: str
    auth_config: Dict[str, Any]         # non-secret fields only
    has_secret: bool = False             # True when secret_ref is set
    default_headers: Dict[str, Any]
    rate_limit_rps: float
    max_concurrency: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Job Config schemas ────────────────────────────────────────────────────────

class JobConfigCreate(BaseModel):
    connection_id: UUID
    name: str
    http_method: str = "GET"
    path_template: str
    query_template: Dict[str, Any] = Field(default_factory=dict)
    body_template: Optional[Dict[str, Any]] = None

    pagination_type: str = "none"
    pagination_config: Dict[str, Any] = Field(default_factory=dict)

    cursor_field_path: Optional[str] = None
    cursor_query_param: Optional[str] = None

    param_source_type: str = "static"
    param_source_config: Dict[str, Any] = Field(default_factory=dict)

    target_bronze_bucket: str = "compassx-bronze"
    schedule_cron: str
    is_enabled: bool = True


class JobConfigUpdate(BaseModel):
    name: Optional[str] = None
    http_method: Optional[str] = None
    path_template: Optional[str] = None
    query_template: Optional[Dict[str, Any]] = None
    body_template: Optional[Dict[str, Any]] = None
    pagination_type: Optional[str] = None
    pagination_config: Optional[Dict[str, Any]] = None
    cursor_field_path: Optional[str] = None
    cursor_query_param: Optional[str] = None
    param_source_type: Optional[str] = None
    param_source_config: Optional[Dict[str, Any]] = None
    target_bronze_bucket: Optional[str] = None
    schedule_cron: Optional[str] = None


class JobConfigOut(BaseModel):
    id: UUID
    workspace_id: UUID
    connection_id: UUID
    name: str
    http_method: str
    path_template: str
    query_template: Dict[str, Any]
    body_template: Optional[Dict[str, Any]]
    pagination_type: str
    pagination_config: Dict[str, Any]
    cursor_field_path: Optional[str]
    cursor_query_param: Optional[str]
    param_source_type: str
    param_source_config: Dict[str, Any]
    target_bronze_bucket: str
    schedule_cron: str
    is_enabled: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Run schemas ───────────────────────────────────────────────────────────────

class RunSummaryOut(BaseModel):
    id: UUID
    job_config_id: UUID
    airflow_dag_run_id: Optional[str]
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    total_params: int
    succeeded_params: int
    failed_params: int
    total_rows_landed: int
    total_bytes_landed: int
    error_summary: Optional[str]

    class Config:
        from_attributes = True


class RunItemOut(BaseModel):
    id: UUID
    run_id: UUID
    param_value: str
    status: str
    pages_fetched: int
    rows_landed: int
    bytes_landed: int
    bronze_path: Optional[str]
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Watermark reset ───────────────────────────────────────────────────────────

class WatermarkResetIn(BaseModel):
    param_value: Optional[str] = None   # None = reset all params for this job


# ── Trigger response ──────────────────────────────────────────────────────────

class TriggerOut(BaseModel):
    run_id: UUID
    status: str = "running"
    message: str = "Run enqueued. Poll GET /runs/{run_id} for status."
