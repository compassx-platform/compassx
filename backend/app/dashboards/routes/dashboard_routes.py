"""
Dashboard routes (prefix: /api/v1/dashboards):

  GET    /api/v1/dashboards                                  — list all (meta only)
  POST   /api/v1/dashboards                                  — create
  GET    /api/v1/dashboards/{id}                             — get full dashboard
  PUT    /api/v1/dashboards/{id}                             — save draft
  DELETE /api/v1/dashboards/{id}                             — delete
  POST   /api/v1/dashboards/{id}/publish                     — publish draft
  POST   /api/v1/dashboards/{id}/discard                     — discard draft (revert to published)
  POST   /api/v1/dashboards/{id}/clone                       — clone
  PUT    /api/v1/dashboards/{id}/pages/{page_id}/layout      — update grid layout for a page
  POST   /api/v1/dashboards/datasets/{dataset_id}/query      — run dataset SQL and return rows
  GET    /api/v1/dashboards/datasets/{dataset_id}/schema     — return column schema
  GET    /api/v1/dashboards/datasets/{dataset_id}/export     — download CSV/TSV/Excel
  GET    /api/v1/dashboards/datasets/{dataset_id}/field-values — distinct values for a field
"""
import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_account_db as get_db, get_system_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.models.dashboard import Dashboard
from app.sql_warehouse.models import SqlWarehouse
from app.sql_warehouse.query.executor import QueryExecutor
from app.sql_warehouse.warehouse.manager import get_warehouse_by_id, list_warehouses

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_meta(d: Dashboard, uc_dash: Any = None) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "folderId": d.folder_id,
        "isDraft": d.is_draft,
        "publishedAt": d.published_at.isoformat() if d.published_at else None,
        "createdBy": d.created_by,
        "permissionMode": d.permission_mode,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
        "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
        "catalog_name": getattr(uc_dash, "catalog_name", None),
        "schema_name": getattr(uc_dash, "schema_name", None),
    }


def _to_full(d: Dashboard) -> dict:
    return {
        **_to_meta(d),
        "pages": d.pages or [],
        "widgets": d.widgets or [],
        "datasets": d.datasets or [],
        "settings": d.settings,
    }


def _securable(db: Session, dashboard_id: str) -> Securable:
    """The catalog path a dashboard is governed at.

    A ``Dashboard`` row is only the stored document; the governed object is
    its registration in the catalog, which is what carries the
    catalog.schema.name path that grants address. A dashboard that has no
    registration cannot be reasoned about, so it is treated as absent rather
    than as ungoverned — otherwise the gap in metadata would be the way past
    the check.
    """
    from app.catalog.models import UnifiedCatalogDashboard

    uc = (
        db.query(UnifiedCatalogDashboard)
        .filter(UnifiedCatalogDashboard.dashboard_id == dashboard_id)
        .first()
    )
    if not uc:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return Securable.dashboard(uc.catalog_name, uc.schema_name, uc.name)


def _authorized_dashboard(
    db: Session, guard: Guard, dashboard_id: str, privilege: Privilege
) -> Dashboard:
    """Load a dashboard the caller holds ``privilege`` on, or raise."""
    d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    guard.require(privilege, _securable(db, dashboard_id))
    return d


def _bind_params(sql: str, params: Dict[str, Any]) -> str:
    """Substitute ``:name`` placeholders with SQL literals.

    Values are quoted and escaped rather than pasted in raw. The previous
    ``sql.replace(f":{key}", str(val))`` meant a filter value of
    ``' OR 1=1 --`` rewrote the dataset's query, so any dashboard viewer could
    read any table the warehouse could reach.

    Substitution happens here rather than through driver bind parameters
    because the SQL is sent as text to a warehouse engine that does not accept
    a parameter list.
    """
    for key, val in (params or {}).items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
            raise HTTPException(status_code=400, detail=f"Invalid parameter name: {key}")
        sql = sql.replace(f":{key}", _sql_literal(val))
    return sql


def _sql_literal(val: Any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, (list, tuple)):
        return ", ".join(_sql_literal(v) for v in val)
    return "'" + str(val).replace("'", "''") + "'"


def _authorized_dataset(
    db: Session, guard: Guard, dataset_id: str
) -> tuple[dict, str]:
    """Find a dataset by id, in a dashboard the caller may browse.

    Dataset ids are searched across every dashboard, so the search itself is
    the access decision: without this, quoting any dataset id ran its SQL —
    and dataset SQL reads warehouse tables. Dashboards the caller cannot
    BROWSE are skipped rather than refused, so the id of a dashboard they
    cannot see is indistinguishable from one that does not exist.
    """
    for d in db.query(Dashboard).all():
        for ds in (d.datasets or []):
            if ds.get("id") != dataset_id:
                continue
            guard.require(Privilege.BROWSE, _securable(db, d.id))
            return ds, d.id
    raise HTTPException(status_code=404, detail="Dataset not found")


def _workspace_id(request: Request) -> str | None:
    workspace = getattr(request.state, "workspace", None)
    return workspace.workspace_id if workspace else None


def _principal_id(request: Request) -> str:
    workspace = getattr(request.state, "workspace", None)
    return workspace.principal_id if workspace else "dashboard"


from app.dependencies import get_current_user

async def _run_dashboard_sql(
    request: Request,
    system_db: Session,
    sql: str,
    *,
    max_rows: int = 10000,
    warehouse_id: str | None = None,
    dashboard_id: str | None = None,
    dataset_id: str | None = None,
) -> dict:
    workspace_id = _workspace_id(request)
    current_user = await get_current_user(request)
    run_by_user_id = current_user.get("id") if current_user else None
    run_by_user_name = current_user.get("name") if current_user else None

    warehouse: SqlWarehouse | None = None
    if warehouse_id:
        warehouse = get_warehouse_by_id(system_db, warehouse_id, workspace_id=workspace_id)
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
    else:
        warehouses = list_warehouses(system_db, workspace_id=workspace_id)
        warehouse = next((w for w in warehouses if w.status == "running"), None)
        if warehouse is None:
            raise HTTPException(
                status_code=400,
                detail="No running SQL warehouse is available for dashboard queries.",
            )

    executor = QueryExecutor(system_db)
    session_id = request.headers.get("x-session-id")
    return await executor.run(
        warehouse=warehouse,
        sql=sql,
        user_id=_principal_id(request),
        session_id=session_id,
        max_rows=max_rows,
        source="dashboard",
        dashboard_id=dashboard_id,
        dataset_id=dataset_id,
        run_by_user_id=run_by_user_id,
        run_by_user_name=run_by_user_name,
    )


# ── Dashboard CRUD ────────────────────────────────────────────────────────────

def _default_schema(db: Session, guard: Guard, workspace_id: str):
    """Resolve the catalog schema a new dashboard is registered under.

    Returns the schema, having first checked that the caller may CREATE in
    it. Provisioning a catalog or schema that does not exist yet is an admin
    action — a member who may add a dashboard to an existing schema is not
    thereby entitled to bring new containers into being.
    """
    from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, CatalogWorkspaceBinding

    binding = (
        db.query(CatalogWorkspaceBinding)
        .filter(CatalogWorkspaceBinding.workspace_id == workspace_id)
        .order_by(CatalogWorkspaceBinding.is_default.desc())
        .first()
    )
    catalog = (
        db.query(UnifiedCatalog).filter(UnifiedCatalog.id == binding.catalog_id).first()
        if binding
        else db.query(UnifiedCatalog).filter(UnifiedCatalog.all_workspaces.is_(True)).first()
    )

    if not catalog:
        guard.require_workspace_admin("Creating the workspace catalog")
        catalog = UnifiedCatalog(
            name=f"workspace_catalog_{workspace_id[:8]}",
            catalog_type="postgres",
            database_name="postgres",
            all_workspaces=False,
            created_by=guard.principal.id,
        )
        db.add(catalog)
        db.flush()
        db.add(
            CatalogWorkspaceBinding(
                catalog_id=catalog.id, workspace_id=workspace_id, is_default=True
            )
        )
        db.flush()

    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id)
        .first()
    )
    if not schema:
        guard.require_workspace_admin("Creating the default schema")
        schema = UnifiedCatalogSchema(
            catalog_id=catalog.id, name="default", created_by=guard.principal.id
        )
        db.add(schema)
        db.flush()

    guard.require(Privilege.CREATE, Securable.schema_(catalog.name, schema.name))
    return catalog, schema


def _rename_registration(
    db: Session, guard: Guard, dashboard_id: str, new_name: str
) -> None:
    """Rename the catalog entry and carry its grants to the new path.

    Grants address a dashboard as catalog.schema.name, so renaming without
    relocating would silently revoke everyone who had access while still
    showing their grants in the UI.
    """
    from app.catalog.models import UnifiedCatalogDashboard

    uc = (
        db.query(UnifiedCatalogDashboard)
        .filter(UnifiedCatalogDashboard.dashboard_id == dashboard_id)
        .first()
    )
    if not uc:
        return
    old = Securable.dashboard(uc.catalog_name, uc.schema_name, uc.name)
    uc.name = new_name
    uc.updated_by = guard.principal.id
    db.flush()
    guard.relocate(old, Securable.dashboard(uc.catalog_name, uc.schema_name, new_name))


def _register_dashboard(
    db: Session, catalog, schema, dashboard_id: str, name: str, actor: str
) -> Securable:
    from app.catalog.models import UnifiedCatalogDashboard

    db.add(
        UnifiedCatalogDashboard(
            schema_id=schema.id,
            catalog_name=catalog.name,
            schema_name=schema.name,
            name=name,
            dashboard_id=dashboard_id,
            owner=actor,
            created_by=actor,
            updated_by=actor,
        )
    )
    db.flush()
    return Securable.dashboard(catalog.name, schema.name, name)


@router.get("")
def list_dashboards(
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    from app.catalog.models import UnifiedCatalogDashboard

    dashboards = db.query(Dashboard).order_by(Dashboard.updated_at.desc()).all()
    uc_dashboards = db.query(UnifiedCatalogDashboard).filter(UnifiedCatalogDashboard.dashboard_id.isnot(None)).all()
    uc_map = {uc.dashboard_id: uc for uc in uc_dashboards}
    # Unregistered dashboards have no catalog path and therefore no grants;
    # they are excluded rather than shown to everyone.
    visible = [
        d
        for d in dashboards
        if d.id in uc_map
        and guard.can(
            Privilege.BROWSE,
            Securable.dashboard(
                uc_map[d.id].catalog_name, uc_map[d.id].schema_name, uc_map[d.id].name
            ),
        )
    ]
    return [_to_meta(d, uc_map.get(d.id)) for d in visible]



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
    dash_id = str(uuid.uuid4())
    first_page_id = str(uuid.uuid4())
    actor = guard.principal.id
    workspace_id = guard.workspace_id
    # Resolve and authorise the destination schema before writing anything:
    # a dashboard that cannot be registered has no catalog path, and an
    # object with no path is one no grant can ever reach.
    catalog, schema = _default_schema(db, guard, workspace_id)

    d = Dashboard(
        id=dash_id,
        name=body.name,
        folder_id=body.folderId,
        permission_mode=body.permissionMode,
        is_draft=True,
        pages=[{
            "id": first_page_id,
            "dashboardId": dash_id,
            "name": "Page 1",
            "order": 0,
            "layout": [],
        }],
        widgets=[],
        datasets=[],
        settings=None,
        created_by=actor,
    )
    db.add(d)
    db.flush()

    securable = _register_dashboard(db, catalog, schema, dash_id, body.name, actor)
    guard.claim_ownership(securable)

    db.commit()
    db.refresh(d)
    return _to_full(d)


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
    """Run dataset SQL through the SQL warehouse engine and return rows."""
    payload = body or {}

    dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

    # The dataset editor previews SQL before it is saved, so an override is
    # accepted — but only from someone who could have saved it and run it
    # anyway. Without this check, a viewer could pass any SQL they liked and
    # the dataset id was decoration on an open query runner.
    override = (payload.get("sql") or "").strip()
    if override:
        guard.require(Privilege.EDIT, _securable(db, dashboard_id))
        sql = override
    else:
        sql = (dataset.get("sql") or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Dataset has no SQL defined")

    sql = _bind_params(sql, payload.get("params", {}))

    warehouse_id = payload.get("warehouse_id")
    try:
        result = await _run_dashboard_sql(request, system_db, sql, warehouse_id=warehouse_id, dashboard_id=dashboard_id, dataset_id=dataset_id)
        return {
            "columns": result["columns"],
            "rows": result["rows"],
            "rowCount": result.get("row_count", result.get("rows_returned", len(result["rows"]))),
            "executionMs": result.get("execution_time_ms", result.get("duration_ms", 0)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query error: {exc}")


@router.get("/datasets/{dataset_id}/schema")
async def dataset_schema(
    dataset_id: str,
    request: Request,
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Return column schema for a dataset by running a zero-row warehouse query."""
    dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

    if dataset.get("schema"):
        return dataset["schema"]

    sql = dataset.get("sql", "").strip()
    if not sql:
        return []

    limit_sql = f"SELECT * FROM ({sql}) _q LIMIT 0"
    try:
        result = await _run_dashboard_sql(
            request, system_db, limit_sql, max_rows=1, 
            warehouse_id=(dataset.get("warehouse_id") if isinstance(dataset, dict) else None),
            dashboard_id=dashboard_id, dataset_id=dataset_id
        )
        return [{"name": col, "type": "unknown"} for col in result["columns"]]
    except HTTPException:
        return []
    except Exception:
        return []


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(
    dataset_id: str,
    request: Request,
    format: str = Query("csv", pattern="^(csv|tsv|excel)$"),
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Download dataset result as CSV/TSV/Excel using the warehouse engine."""
    dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

    sql = dataset.get("sql", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Dataset has no SQL defined")

    try:
        result = await _run_dashboard_sql(
            request,
            system_db,
            sql,
            max_rows=100_000,
            warehouse_id=dataset.get("warehouse_id"),
            dashboard_id=dashboard_id,
            dataset_id=dataset_id,
        )
        columns = result["columns"]
        rows = [
            [row.get(col) if isinstance(row, dict) else (row[idx] if idx < len(row) else None) for idx, col in enumerate(columns)]
            for row in result["rows"]
        ]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query error: {exc}")

    if format == "excel":
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(columns)
            for row in rows[:100_000]:
                ws.append(row)
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=dataset.xlsx"},
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed")

    delimiter = "\t" if format == "tsv" else ","
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter)
    writer.writerow(columns)
    writer.writerows(rows)
    buf.seek(0)
    ext = "tsv" if format == "tsv" else "csv"
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=dataset.{ext}"},
    )


@router.get("/datasets/{dataset_id}/field-values")
async def field_values(
    dataset_id: str,
    request: Request,
    field: str = Query(...),
    db: Session = Depends(get_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Return distinct values for a field in the dataset."""
    dataset, dashboard_id = _authorized_dataset(db, guard, dataset_id)

    sql = dataset.get("sql", "").strip()
    if not sql:
        return []

    # ``field`` is interpolated into the query as an identifier, so it is
    # restricted to identifier characters. Stripping double quotes was not
    # enough: a backslash or a comment sequence still escaped the position.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*", field):
        raise HTTPException(status_code=400, detail="Invalid field name")
    distinct_sql = f'SELECT DISTINCT "{field}" FROM ({sql}) _q WHERE "{field}" IS NOT NULL ORDER BY 1 LIMIT 1000'
    try:
        result = await _run_dashboard_sql(
            request,
            system_db,
            distinct_sql,
            max_rows=1000,
            warehouse_id=dataset.get("warehouse_id"),
            dashboard_id=dashboard_id,
            dataset_id=dataset_id,
        )
        if not result["columns"]:
            return []
        col = result["columns"][0]
        return [str(row.get(col, "")) if isinstance(row, dict) else str(row[0] if row else "") for row in result["rows"]]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query error: {exc}")


@router.get("/{dashboard_id}")
def get_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    d = _authorized_dashboard(db, guard, dashboard_id, Privilege.BROWSE)
    return _to_full(d)


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
    d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
    if body.name is not None and body.name != d.name:
        _rename_registration(db, guard, dashboard_id, body.name)
    if body.name is not None:
        d.name = body.name
    if body.pages is not None:
        d.pages = body.pages
    if body.widgets is not None:
        d.widgets = body.widgets
    if body.datasets is not None:
        d.datasets = body.datasets
    if body.settings is not None:
        d.settings = body.settings
    if body.permissionMode is not None:
        d.permission_mode = body.permissionMode
    if body.folderId is not None:
        d.folder_id = body.folderId
    db.commit()
    db.refresh(d)
    return _to_full(d)


@router.delete("/{dashboard_id}", status_code=204)
def delete_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    d = _authorized_dashboard(db, guard, dashboard_id, Privilege.MANAGE)
    from app.catalog.models import UnifiedCatalogDashboard
    db.query(UnifiedCatalogDashboard).filter(UnifiedCatalogDashboard.dashboard_id == dashboard_id).delete()
    db.delete(d)
    db.commit()


@router.post("/{dashboard_id}/publish")
def publish_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
    d.is_draft = False
    d.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    return _to_full(d)


@router.post("/{dashboard_id}/discard")
def discard_draft(
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Discard draft edits — resets is_draft to True (no snapshot store for v1)."""
    d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
    d.is_draft = True
    db.commit()
    db.refresh(d)
    return _to_full(d)


@router.post("/{dashboard_id}/clone")
def clone_dashboard(
    request: Request,
    dashboard_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    # A clone copies the source's widgets and dataset SQL verbatim into an
    # object the caller will own, so it discloses everything BROWSE does —
    # and no more. The destination is authorised separately below.
    src = _authorized_dashboard(db, guard, dashboard_id, Privilege.BROWSE)
    new_id = str(uuid.uuid4())
    actor = guard.principal.id
    catalog, schema = _default_schema(db, guard, guard.workspace_id)

    import copy
    new_pages = copy.deepcopy(src.pages or [])
    new_widgets = copy.deepcopy(src.widgets or [])
    new_datasets = copy.deepcopy(src.datasets or [])

    # Remap page and widget IDs so they're independent
    page_id_map: Dict[str, str] = {}
    for page in new_pages:
        old_id = page["id"]
        new_pid = str(uuid.uuid4())
        page_id_map[old_id] = new_pid
        page["id"] = new_pid
        page["dashboardId"] = new_id

    for widget in new_widgets:
        widget["id"] = str(uuid.uuid4())
        if widget.get("pageId") in page_id_map:
            widget["pageId"] = page_id_map[widget["pageId"]]

    for ds in new_datasets:
        ds["id"] = str(uuid.uuid4())
        ds["dashboardId"] = new_id

    clone = Dashboard(
        id=new_id,
        name=f"{src.name} (copy)",
        folder_id=src.folder_id,
        permission_mode=src.permission_mode,
        is_draft=True,
        pages=new_pages,
        widgets=new_widgets,
        datasets=new_datasets,
        settings=copy.deepcopy(src.settings),
        created_by=actor,
    )
    db.add(clone)
    db.flush()

    securable = _register_dashboard(
        db, catalog, schema, new_id, f"{src.name} (copy)", actor
    )
    guard.claim_ownership(securable)

    db.commit()
    db.refresh(clone)
    return _to_full(clone)


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
    d = _authorized_dashboard(db, guard, dashboard_id, Privilege.EDIT)
    pages = d.pages or []
    found = False
    for page in pages:
        if page.get("id") == page_id:
            page["layout"] = body.layout
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Page not found")
    d.pages = pages
    db.commit()
    db.refresh(d)
    return _to_full(d)
