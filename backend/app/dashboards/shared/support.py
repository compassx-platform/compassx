"""Shared dashboard lookups, catalog registration, and warehouse query execution."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.models.dashboard import Dashboard
from app.sql_warehouse.models import SqlWarehouse
from app.sql_warehouse.query.executor import QueryExecutor
from app.sql_warehouse.warehouse.manager import get_warehouse_by_id, list_warehouses


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
