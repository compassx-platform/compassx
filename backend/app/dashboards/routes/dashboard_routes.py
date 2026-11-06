"""
Dashboard routes (prefix: /api/v1/dashboards).

Handlers stay here. Each one forwards to one application type.
Helper names stay importable from this module.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_account_db as get_db, get_system_db
from app.governance.dependencies import Guard, get_guard
from app.dashboards.dataset.application.dataset_schema import dataset_schema as dataset_schema_action
from app.dashboards.dataset.application.export_dataset import export_dataset as export_dataset_action
from app.dashboards.dataset.application.field_values import field_values as field_values_action
from app.dashboards.dataset.application.query_dataset import query_dataset as query_dataset_action
from app.dashboards.document.application.clone_dashboard import clone_dashboard as clone_dashboard_action
from app.dashboards.document.application.create_dashboard import create_dashboard as create_dashboard_action
from app.dashboards.document.application.delete_dashboard import delete_dashboard as delete_dashboard_action
from app.dashboards.document.application.discard_draft import discard_draft as discard_draft_action
from app.dashboards.document.application.get_dashboard import get_dashboard as get_dashboard_action
from app.dashboards.document.application.list_dashboards import list_dashboards as list_dashboards_action
from app.dashboards.document.application.publish_dashboard import publish_dashboard as publish_dashboard_action
from app.dashboards.document.application.save_dashboard import save_dashboard as save_dashboard_action
from app.dashboards.document.application.update_page_layout import update_page_layout as update_page_layout_action
from app.dashboards.shared.support import (
    _authorized_dashboard,
    _authorized_dataset,
    _bind_params,
    _default_schema,
    _principal_id,
    _register_dashboard,
    _rename_registration,
    _run_dashboard_sql,
    _securable,
    _sql_literal,
    _to_full,
    _to_meta,
    _utcnow_iso,
    _workspace_id,
)

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


@router.get("")
def list_dashboards(
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return list_dashboards_action(request, db, guard)


class CreateBody(BaseModel):
    name: str
    folderId: Optional[str] = None
    permissionMode: str = "individual"


@router.post("", status_code=201)
def create_dashboard(
    request: Request,
    body: CreateBody,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return create_dashboard_action(request, body, db, guard)


@router.get("/datasets/{dataset_id}/query", include_in_schema=False)
@router.post("/datasets/{dataset_id}/query")
async def query_dataset(
    dataset_id: str,
    request: Request,
    body: Dict[str, Any] | None = None,
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return await query_dataset_action(dataset_id, request, body, db, system_db, guard)


@router.get("/datasets/{dataset_id}/schema")
async def dataset_schema(
    dataset_id: str,
    request: Request,
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return await dataset_schema_action(dataset_id, request, db, system_db, guard)


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(
    dataset_id: str,
    request: Request,
    format: str = Query("csv", pattern="^(csv|tsv|excel)$"),
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return await export_dataset_action(dataset_id, request, format, db, system_db, guard)


@router.get("/datasets/{dataset_id}/field-values")
async def field_values(
    dataset_id: str,
    request: Request,
    field: str = Query(...),
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return await field_values_action(dataset_id, request, field, db, system_db, guard)


@router.get("/{dashboard_id}")
def get_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return get_dashboard_action(dashboard_id, db, guard)


class SaveBody(BaseModel):
    name: Optional[str] = None
    pages: Optional[List[Any]] = None
    widgets: Optional[List[Any]] = None
    datasets: Optional[List[Any]] = None
    settings: Optional[Any] = None
    permissionMode: Optional[str] = None
    folderId: Optional[str] = None


@router.put("/{dashboard_id}")
def save_dashboard(
    dashboard_id: str,
    body: SaveBody,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return save_dashboard_action(dashboard_id, body, db, guard)


@router.delete("/{dashboard_id}", status_code=204)
def delete_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return delete_dashboard_action(dashboard_id, db, guard)


@router.post("/{dashboard_id}/publish")
def publish_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return publish_dashboard_action(dashboard_id, db, guard)


@router.post("/{dashboard_id}/discard")
def discard_draft(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return discard_draft_action(dashboard_id, db, guard)


@router.post("/{dashboard_id}/clone")
def clone_dashboard(
    request: Request,
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return clone_dashboard_action(request, dashboard_id, db, guard)


class LayoutBody(BaseModel):
    layout: List[Any]


@router.put("/{dashboard_id}/pages/{page_id}/layout")
def update_page_layout(
    dashboard_id: str,
    page_id: str,
    body: LayoutBody,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return update_page_layout_action(dashboard_id, page_id, body, db, guard)
