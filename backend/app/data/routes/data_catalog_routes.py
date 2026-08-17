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

@router.get("/connections", response_model=list[ConnectionResponse])
def get_connections(db: Session = Depends(get_db)):
    return list_connections(db)


@router.get("/connections/{conn_id}", response_model=ConnectionResponse)
def read_connection(conn_id: int, db: Session = Depends(get_db)):
    record = get_connection(db, conn_id)
    if not record:
        raise HTTPException(status_code=404, detail="Connection not found")
    return record


@router.post("/connections", response_model=ConnectionResponse, status_code=201)
def add_connection(body: ConnectionCreate, db: Session = Depends(get_db)):
    return create_connection(db, body)


@router.put("/connections/{conn_id}", response_model=ConnectionResponse)
def edit_connection(conn_id: int, body: ConnectionUpdate, db: Session = Depends(get_db)):
    record = update_connection(db, conn_id, body)
    if not record:
        raise HTTPException(status_code=404, detail="Connection not found")
    return record


@router.delete("/connections/{conn_id}", status_code=204)
def remove_connection(conn_id: int, db: Session = Depends(get_db)):
    if not delete_connection(db, conn_id):
        raise HTTPException(status_code=404, detail="Connection not found")


# ── Connection test ───────────────────────────────────────────────────────────

@router.post("/connections/test", response_model=ConnectionTestResponse)
def test_connection(body: ConnectionTestRequest):
    result = test_connection_raw(
        host=body.host,
        port=body.port,
        username=body.username,
        password=body.password,
        database=body.database,
    )
    return ConnectionTestResponse(**result)


# ── Catalog browsing ──────────────────────────────────────────────────────────

@router.get("/{conn_id}/databases", response_model=DatabaseListResponse)
def get_databases(conn_id: int, db: Session = Depends(get_db)):
    try:
        dbs = list_databases(db, conn_id)
        return DatabaseListResponse(databases=[DatabaseItem(**d) for d in dbs])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{conn_id}/databases/{database}/schemas", response_model=SchemaListResponse)
def get_schemas(conn_id: int, database: str, db: Session = Depends(get_db)):
    try:
        schemas = list_schemas(db, conn_id, database)
        return SchemaListResponse(schemas=[SchemaItem(**s) for s in schemas])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/{conn_id}/databases/{database}/schemas/{schema}/tables",
    response_model=TableListResponse,
)
def get_tables(conn_id: int, database: str, schema: str, db: Session = Depends(get_db)):
    try:
        tables = list_tables(db, conn_id, database, schema)
        return TableListResponse(tables=[TableItem(**t) for t in tables])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    try:
        return get_table_preview(db, conn_id, database, schema, table, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── SQL execution ─────────────────────────────────────────────────────────────

@router.post("/sql/execute", response_model=SqlExecuteResponse)
def run_sql(body: SqlExecuteRequest, db: Session = Depends(get_db)):
    try:
        return execute_sql(db, body.connection_id, body.database, body.sql, body.limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))