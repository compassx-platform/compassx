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


from app.data.http.catalog.application.get_connections import get_connections as get_connections_action
from app.data.http.catalog.application.read_connection import read_connection as read_connection_action
from app.data.http.catalog.application.add_connection import add_connection as add_connection_action
from app.data.http.catalog.application.edit_connection import edit_connection as edit_connection_action
from app.data.http.catalog.application.remove_connection import remove_connection as remove_connection_action
from app.data.http.catalog.application.test_connection import test_connection as test_connection_action
from app.data.http.catalog.application.get_databases import get_databases as get_databases_action
from app.data.http.catalog.application.get_schemas import get_schemas as get_schemas_action
from app.data.http.catalog.application.get_tables import get_tables as get_tables_action
from app.data.http.catalog.application.preview_table import preview_table as preview_table_action
from app.data.http.catalog.application.run_sql import run_sql as run_sql_action

@router.get("/connections", response_model=list[ConnectionResponse])
def get_connections(db: Session = Depends(get_db)):
    from app.data.http.catalog.application.get_connections import get_connections as get_connections_action
    return get_connections_action(db=db)

@router.get("/connections/{conn_id}", response_model=ConnectionResponse)
def read_connection(conn_id: int, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.read_connection import read_connection as read_connection_action
    return read_connection_action(conn_id=conn_id, db=db)

@router.post("/connections", response_model=ConnectionResponse, status_code=201)
def add_connection(body: ConnectionCreate, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.add_connection import add_connection as add_connection_action
    return add_connection_action(body=body, db=db)

@router.put("/connections/{conn_id}", response_model=ConnectionResponse)
def edit_connection(conn_id: int, body: ConnectionUpdate, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.edit_connection import edit_connection as edit_connection_action
    return edit_connection_action(conn_id=conn_id, body=body, db=db)

@router.delete("/connections/{conn_id}", status_code=204)
def remove_connection(conn_id: int, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.remove_connection import remove_connection as remove_connection_action
    return remove_connection_action(conn_id=conn_id, db=db)

@router.post("/connections/test", response_model=ConnectionTestResponse)
def test_connection(body: ConnectionTestRequest):
    from app.data.http.catalog.application.test_connection import test_connection as test_connection_action
    return test_connection_action(body=body)

@router.get("/{conn_id}/databases", response_model=DatabaseListResponse)
def get_databases(conn_id: int, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.get_databases import get_databases as get_databases_action
    return get_databases_action(conn_id=conn_id, db=db)

@router.get("/{conn_id}/databases/{database}/schemas", response_model=SchemaListResponse)
def get_schemas(conn_id: int, database: str, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.get_schemas import get_schemas as get_schemas_action
    return get_schemas_action(conn_id=conn_id, database=database, db=db)

@router.get(
    "/{conn_id}/databases/{database}/schemas/{schema}/tables",
    response_model=TableListResponse,
)
def get_tables(conn_id: int, database: str, schema: str, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.get_tables import get_tables as get_tables_action
    return get_tables_action(conn_id=conn_id, database=database, schema=schema, db=db)

@router.get(
    "/{conn_id}/databases/{database}/schemas/{schema}/tables/{table}/preview",
    response_model=TablePreviewResponse,
)
def preview_table(
    conn_id: int,
    database: str,
    schema: str,
    table: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    from app.data.http.catalog.application.preview_table import preview_table as preview_table_action
    return preview_table_action(conn_id=conn_id, database=database, schema=schema, table=table, limit=limit, db=db)

@router.post("/sql/execute", response_model=SqlExecuteResponse)
def run_sql(body: SqlExecuteRequest, db: Session = Depends(get_db)):
    from app.data.http.catalog.application.run_sql import run_sql as run_sql_action
    return run_sql_action(body=body, db=db)
