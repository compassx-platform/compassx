"""
SQL warehouse routes (prefix: /api/v1).

Handlers stay here. Each one forwards to one application type.
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_account_db, get_system_db
from app.dependencies import get_current_user
from app.sql_warehouse.catalog.application.list_catalogs import list_catalogs as list_catalogs_action
from app.sql_warehouse.catalog.application.list_columns import list_columns as list_columns_action
from app.sql_warehouse.catalog.application.list_schemas import list_schemas as list_schemas_action
from app.sql_warehouse.catalog.application.list_tables import list_tables as list_tables_action
from app.sql_warehouse.draft.application.create_draft import create_draft as create_draft_action
from app.sql_warehouse.draft.application.delete_draft import delete_draft as delete_draft_action
from app.sql_warehouse.draft.application.list_drafts import list_drafts as list_drafts_action
from app.sql_warehouse.draft.application.update_draft import update_draft as update_draft_action
from app.sql_warehouse.query.application.cancel_query import cancel_query as cancel_query_action
from app.sql_warehouse.query.application.explain_query import explain_query as explain_query_action
from app.sql_warehouse.query.application.get_result import get_result as get_result_action
from app.sql_warehouse.query.application.query_history import query_history as query_history_action
from app.sql_warehouse.query.application.run_query import run_query as run_query_action
from app.sql_warehouse.query.application.validate_query import validate_query as validate_query_action
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
from app.sql_warehouse.shared.support import _record_to_dict, _resolve_user_and_workspace
from app.sql_warehouse.warehouse.application.create_warehouse_http import create_wh as create_wh_action
from app.sql_warehouse.warehouse.application.delete_warehouse_http import delete_wh as delete_wh_action
from app.sql_warehouse.warehouse.application.get_warehouse_http import get_wh as get_wh_action
from app.sql_warehouse.warehouse.application.health import health as health_action
from app.sql_warehouse.warehouse.application.list_warehouses_http import list_wh as list_wh_action
from app.sql_warehouse.warehouse.application.set_default_warehouse_http import set_default_wh as set_default_wh_action
from app.sql_warehouse.warehouse.application.start_warehouse import start_wh as start_wh_action
from app.sql_warehouse.warehouse.application.stop_warehouse import stop_wh as stop_wh_action

router = APIRouter(prefix="/api/v1", tags=["sql-warehouse"])


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_wh(request: Request, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return list_wh_action(request, db, user)


@router.post("/warehouses", response_model=WarehouseRead)
async def create_wh(request: Request, req: WarehouseCreate, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return await create_wh_action(request, req, db, user)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseRead)
def get_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return get_wh_action(request, warehouse_id, db, user)


@router.post("/warehouses/{warehouse_id}/start", response_model=WarehouseRead)
async def start_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return await start_wh_action(request, warehouse_id, db, user)


@router.post("/warehouses/{warehouse_id}/stop", response_model=WarehouseRead)
async def stop_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return await stop_wh_action(request, warehouse_id, db, user)


@router.post("/warehouses/{warehouse_id}/set-default", response_model=WarehouseRead)
def set_default_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return set_default_wh_action(request, warehouse_id, db, user)


@router.delete("/warehouses/{warehouse_id}")
async def delete_wh(request: Request, warehouse_id: str, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return await delete_wh_action(request, warehouse_id, db, user)


@router.post("/sql/query")
async def run_query(
    request: Request,
    req: QueryRequest,
    db: Session = Depends(get_system_db),
    data_db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    return await run_query_action(request, req, db, data_db, user)


@router.post("/sql/explain")
async def explain_query(request: Request, req: ExplainRequest, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return await explain_query_action(request, req, db, user)


@router.post("/sql/validate")
def validate_query(req: ValidateRequest, user=Depends(get_current_user)):
    return validate_query_action(req, user)


@router.post("/sql/cancel")
async def cancel_query(
    request: Request,
    req: CancelRequest,
    db: Session = Depends(get_system_db),
    data_db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    return await cancel_query_action(request, req, db, data_db, user)


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
    return query_history_action(request, warehouse_id, limit, offset, status, scope, db, user)


@router.get("/sql/result/{query_id}")
def get_result(query_id: str, request: Request, db: Session = Depends(get_system_db), user=Depends(get_current_user)):
    return get_result_action(query_id, request, db, user)


@router.get("/sql/drafts", response_model=list[SqlDraftRead])
def list_drafts(
    request: Request,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    return list_drafts_action(request, db, user)


@router.post("/sql/drafts", response_model=SqlDraftRead)
def create_draft(
    request: Request,
    req: SqlDraftCreate,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    return create_draft_action(request, req, db, user)


@router.put("/sql/drafts/{draft_id}", response_model=SqlDraftRead)
def update_draft(
    draft_id: str,
    req: SqlDraftUpdate,
    request: Request,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    return update_draft_action(draft_id, req, request, db, user)


@router.delete("/sql/drafts/{draft_id}")
def delete_draft(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_system_db),
    user=Depends(get_current_user),
):
    return delete_draft_action(draft_id, request, db, user)


@router.get("/sql-warehouse/catalog/catalogs")
async def list_catalogs(request: Request, db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    return await list_catalogs_action(request, db, user)


@router.get("/sql-warehouse/catalog/schemas")
async def list_schemas(request: Request, catalog: str = Query("default"), db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    return await list_schemas_action(request, catalog, db, user)


@router.get("/sql-warehouse/catalog/tables")
async def list_tables(request: Request, catalog: str = Query("default"), schema: str = Query("public"), db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    return await list_tables_action(request, catalog, schema, db, user)


@router.get("/sql-warehouse/catalog/columns")
async def list_columns(request: Request, catalog: str = Query("default"), schema: str = Query("public"), table: str = Query(...), db: Session = Depends(get_account_db), user=Depends(get_current_user)):
    return await list_columns_action(request, catalog, schema, table, db, user)


@router.get("/sql-warehouse/health")
def health(db: Session = Depends(get_system_db)):
    return health_action(db)
