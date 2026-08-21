from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WarehouseCreate(BaseModel):
    name: str
    description: str | None = None
    engine: str = "duckdb"
    config: dict[str, Any] = Field(default_factory=dict)
    resource_policy: dict[str, Any] = Field(default_factory=dict)


class WarehouseRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    engine: str
    status: str
    config: dict[str, Any]
    resource_policy: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    warehouse_id: str
    sql: str
    session_id: str | None = None
    catalog: str | None = None
    schema_name: str | None = None
    source: str = "sql_editor"
    max_rows: int = Field(default=10000, ge=1, le=100000)


class ExplainRequest(BaseModel):
    warehouse_id: str
    sql: str


class ValidateRequest(BaseModel):
    sql: str
    dialect: str = "duckdb"


class CancelRequest(BaseModel):
    query_id: str


class NotebookQueryRequest(BaseModel):
    query: str
    warehouse: str | None = None
    timeout_seconds: int = 120


class SqlDraftCreate(BaseModel):
    name: str | None = None
    sql_text: str = ""
    catalog: str | None = ""
    schema_name: str | None = ""
    tab_order: int = 0


class SqlDraftUpdate(BaseModel):
    name: str | None = None
    sql_text: str | None = None
    catalog: str | None = None
    schema_name: str | None = None
    tab_order: int | None = None


class SqlDraftRead(BaseModel):
    id: str
    workspace_id: str | None = None
    user_id: str
    name: str
    sql_text: str
    catalog: str | None = None
    schema_name: str | None = None
    tab_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

