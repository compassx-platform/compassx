from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import get_account_db, get_system_db
from app.dependencies import get_current_user
from app.sql_warehouse.catalog.metadata_api import CatalogMetadataAPI
from app.sql_warehouse.engine.router import get_adapter
from app.sql_warehouse.models import SqlDraftQuery, SqlQueryRecord
from app.sql_warehouse.query.executor import QueryExecutor
from app.sql_warehouse.query.parser import validate_sql, extract_table_references
from app.sql_warehouse.query.query_record import QueryRecordStore
from app.sql_warehouse.schemas import (
    CancelRequest,
    ExplainRequest,
    NotebookQueryRequest,
    QueryRequest,
    SqlDraftCreate,
    SqlDraftRead,
    SqlDraftUpdate,
    ValidateRequest,
    WarehouseCreate,
    WarehouseRead,
)
from app.sql_warehouse.warehouse.manager import create_warehouse, delete_warehouse, get_warehouse_by_id, list_warehouses, update_warehouse_status

router = APIRouter(prefix="/api/v1", tags=["sql-warehouse"])


def _resolve_user_and_workspace(request: Request, user: Any = None) -> tuple[str, str | None]:
    ws_ctx = getattr(request.state, "workspace", None)
    workspace_id = ws_ctx.workspace_id if ws_ctx and hasattr(ws_ctx, "workspace_id") else None
    if not workspace_id:
        workspace_id = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id")

    user_id = None
    if ws_ctx and getattr(ws_ctx, "principal_id", None):
        user_id = ws_ctx.principal_id
    elif isinstance(user, dict):
        user_id = user.get("id") or user.get("sub")
    elif hasattr(user, "id"):
        user_id = user.id

    if not user_id:
        user_id = "bbbbbbbb-0000-0000-0000-000000000001"

    return str(user_id), str(workspace_id) if workspace_id else None



def _record_to_dict(record: SqlQueryRecord) -> dict:
    return {
        "id": record.id,
        "warehouse_id": record.warehouse_id,
        "session_id": record.session_id,
        "user_id": record.user_id,
        "sql_text": record.sql_text,
        "sql_hash": record.sql_hash,
        "status": record.status,
        "engine": record.engine,
        "source": record.source,
        "dashboard_id": record.dashboard_id,
        "dataset_id": record.dataset_id,
        "run_by_user_id": record.run_by_user_id,
        "run_by_user_name": record.run_by_user_name,
        "rows_returned": record.rows_returned,
        "bytes_scanned": record.bytes_scanned,
        "duration_ms": record.duration_ms,
        "error_message": record.error_message,
        "cache_hit": record.cache_hit,
        "query_analysis": record.query_analysis,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "created_at": record.created_at,
    }


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_wh(request: Request, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    _user_id, workspace_id = _resolve_user_and_workspace(request, user)
    return list_warehouses(db, workspace_id=workspace_id)


@router.post("/warehouses", response_model=WarehouseRead)
def create_wh(request: Request, req: WarehouseCreate, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    return create_warehouse(db, req, created_by=user_id, workspace_id=workspace_id)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseRead)
def get_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    _user_id, workspace_id = _resolve_user_and_workspace(request, user)
    wh = get_warehouse_by_id(db, warehouse_id, workspace_id=workspace_id)
    if not wh:
        raise HTTPException(404, "Warehouse not found")
    return wh


@router.post("/warehouses/{warehouse_id}/start", response_model=WarehouseRead)
def start_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    _user_id, workspace_id = _resolve_user_and_workspace(request, user)
    return update_warehouse_status(db, warehouse_id, "running", workspace_id=workspace_id)


@router.post("/warehouses/{warehouse_id}/stop", response_model=WarehouseRead)
def stop_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    _user_id, workspace_id = _resolve_user_and_workspace(request, user)
    return update_warehouse_status(db, warehouse_id, "stopped", workspace_id=workspace_id)


@router.delete("/warehouses/{warehouse_id}")
def delete_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    _user_id, workspace_id = _resolve_user_and_workspace(request, user)
    delete_warehouse(db, warehouse_id, workspace_id=workspace_id)
    return {"deleted": True}


@router.post("/sql/query")
async def run_query(
    request: Request,
    req: QueryRequest,
    db: Session = Depends(get_system_db),
    data_db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    warehouse = get_warehouse_by_id(db, req.warehouse_id, workspace_id=workspace_id)
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")
    if warehouse.status != "running":
        raise HTTPException(400, f"Warehouse is {warehouse.status}, not running")
    try:
        result = await QueryExecutor(db, data_db).run(
            warehouse=warehouse,
            sql=req.sql,
            user_id=user_id,
            session_id=req.session_id,
            max_rows=req.max_rows,
            catalog=req.catalog,
            schema_name=req.schema_name,
            source=req.source,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": "Query execution failed", "detail": str(exc)}) from exc

@router.post("/sql/explain")
async def explain_query(request: Request, req: ExplainRequest, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    del user
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    warehouse = get_warehouse_by_id(db, req.warehouse_id, workspace_id=workspace_id)
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")
    return {"plan": await get_adapter(warehouse).explain(req.sql)}


@router.post("/sql/validate")
def validate_query(req: ValidateRequest, user=Depends(get_current_user)):
    del user
    return validate_sql(req.sql, req.dialect)


@router.post("/sql/cancel")
async def cancel_query(
    request: Request,
    req: CancelRequest,
    db: Session = Depends(get_system_db),
    data_db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    del user
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    records = QueryRecordStore(data_db)
    active = records.get_active(req.query_id)
    if not active:
        raise HTTPException(404, "Query not found or already completed")
    warehouse = get_warehouse_by_id(db, active.warehouse_id, workspace_id=workspace_id)
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")
    await get_adapter(warehouse).cancel(active.engine_query_id or active.query_id)
    records.set_status(req.query_id, "cancelled")
    records.deregister_active(req.query_id)
    return {"cancelled": True, "query_id": req.query_id}


@router.get("/sql/history")
def query_history(
    request: Request,
    warehouse_id: str | None = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    status: str | None = Query(None),
    scope: str = Query("me"),
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    target_user_id = user_id if scope == "me" else None
    records = QueryRecordStore(db).list(user_id=target_user_id, warehouse_id=warehouse_id, status=status, limit=limit, offset=offset)
    return {"records": [_record_to_dict(r) for r in records], "limit": limit, "offset": offset}


@router.get("/sql/result/{query_id}")
def get_result(query_id: str, request: Request, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    record = QueryRecordStore(db).get(query_id)
    if not record:
        raise HTTPException(404, "Query not found")
    if record.user_id != user_id:
        raise HTTPException(403, "Forbidden")
    if record.result_payload:
        return {**record.result_payload, "query_id": query_id, "cache_hit": record.cache_hit, "query_analysis": record.query_analysis}
    return {"query_id": query_id, "status": record.status, "message": "Result no longer available. Re-run the query."}


# ── Draft Queries (Workspace & User Scoped) ──────────────────────────────────

@router.get("/sql/drafts", response_model=list[SqlDraftRead])
def list_drafts(
    request: Request,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    stmt = select(SqlDraftQuery).where(SqlDraftQuery.user_id == user_id)
    if workspace_id:
        stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
    else:
        stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))
    stmt = stmt.order_by(SqlDraftQuery.tab_order.asc(), SqlDraftQuery.created_at.asc())
    return list(db.scalars(stmt))


@router.post("/sql/drafts", response_model=SqlDraftRead)
def create_draft(
    request: Request,
    req: SqlDraftCreate,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)

    # Resolve default query name if none or empty provided
    name = (req.name or "").strip()
    if not name:
        stmt = select(func.count()).select_from(SqlDraftQuery).where(SqlDraftQuery.user_id == user_id)
        if workspace_id:
            stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
        else:
            stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))
        count = db.scalar(stmt) or 0
        name = f"Query {count + 1}"

    draft = SqlDraftQuery(
        workspace_id=workspace_id,
        user_id=user_id,
        name=name,
        sql_text=req.sql_text or "",
        catalog=req.catalog or "",
        schema_name=req.schema_name or "",
        tab_order=req.tab_order,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/sql/drafts/{draft_id}", response_model=SqlDraftRead)
def update_draft(
    draft_id: str,
    req: SqlDraftUpdate,
    request: Request,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    stmt = select(SqlDraftQuery).where(
        SqlDraftQuery.id == draft_id,
        SqlDraftQuery.user_id == user_id,
    )
    if workspace_id:
        stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
    else:
        stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))

    draft = db.scalar(stmt)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft query not found")

    if req.name is not None:
        trimmed_name = req.name.strip()
        if trimmed_name:
            draft.name = trimmed_name
    if req.sql_text is not None:
        draft.sql_text = req.sql_text
    if req.catalog is not None:
        draft.catalog = req.catalog
    if req.schema_name is not None:
        draft.schema_name = req.schema_name
    if req.tab_order is not None:
        draft.tab_order = req.tab_order

    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/sql/drafts/{draft_id}")
def delete_draft(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    user_id, workspace_id = _resolve_user_and_workspace(request, user)
    stmt = select(SqlDraftQuery).where(
        SqlDraftQuery.id == draft_id,
        SqlDraftQuery.user_id == user_id,
    )
    if workspace_id:
        stmt = stmt.where(SqlDraftQuery.workspace_id == workspace_id)
    else:
        stmt = stmt.where(SqlDraftQuery.workspace_id.is_(None))

    draft = db.scalar(stmt)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft query not found")

    db.delete(draft)
    db.commit()
    return {"deleted": True, "id": draft_id}


@router.get("/sql-warehouse/catalog/catalogs")
async def list_catalogs(request: Request, db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    del user
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_catalogs()


@router.get("/sql-warehouse/catalog/schemas")
async def list_schemas(request: Request, catalog: str = Query("default"), db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    del user
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_schemas(catalog)


@router.get("/sql-warehouse/catalog/tables")
async def list_tables(request: Request, catalog: str = Query("default"), schema: str = Query("public"), db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    del user
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_tables(catalog, schema)


@router.get("/sql-warehouse/catalog/columns")
async def list_columns(request: Request, catalog: str = Query("default"), schema: str = Query("public"), table: str = Query(...), db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    del user
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return await CatalogMetadataAPI(db, workspace_id=workspace_id).list_columns(catalog, schema, table)


@router.get("/sql-warehouse/health")
def health(db: Session = Depends(get_system_db)):
    postgres = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        postgres = False
    return {"status": "ok" if postgres else "degraded", "postgres": postgres, "cache": True}




