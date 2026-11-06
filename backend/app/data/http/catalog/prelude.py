"""Data Catalog API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.data_catalog import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    DatabaseListResponse,
    DatabaseItem,
    SchemaListResponse,
    SchemaItem,
    TableListResponse,
    TableItem,
    TablePreviewResponse,
    SqlExecuteRequest,
    SqlExecuteResponse,
)
from app.services.data_catalog_service import (
    list_connections,
    get_connection,
    create_connection,
    update_connection,
    delete_connection,
    test_connection_raw,
    list_databases,
    list_schemas,
    list_tables,
    get_table_preview,
    execute_sql,
)

router = APIRouter(prefix="/api/v1/data-catalog", tags=["Data Catalog"])


# ── Connection CRUD ───────────────────────────────────────────────────────────











# ── Connection test ───────────────────────────────────────────────────────────



# ── Catalog browsing ──────────────────────────────────────────────────────────









# ── SQL execution ─────────────────────────────────────────────────────────────

