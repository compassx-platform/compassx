"""Apps and dashboards that belong to one workspace.

Apps are stored with a workspace id. Dashboards are account-wide rows and
belong to a workspace only through a catalog bound to that workspace.
"""
from __future__ import annotations

from typing import Any, Optional


def selected_workspace_id(workspace_id, workspace_slug, guard, adb) -> str:
    """Workspace the caller named, then the workspace already on the request."""
    if workspace_id:
        return str(workspace_id)
    if workspace_slug and adb is not None:
        from app.workspace.models import Workspace

        try:
            row = adb.query(Workspace).filter(Workspace.slug == workspace_slug).first()
        except KeyError:
            row = None
        if row is not None and getattr(row, "id", None):
            return str(row.id)
    resolved = getattr(guard, "workspace_id", None)
    return str(resolved) if resolved else ""


def workspace_apps(sdb, workspace_id: Optional[str], workspace_slug: Optional[str] = None):
    from app.models.app import App

    apps = sdb.query(App).order_by(App.created_at.desc()).all()
    if workspace_id and workspace_id != "default":
        return [app for app in apps if str(getattr(app, "workspace_id", "")) == str(workspace_id)]
    if workspace_slug:
        return [app for app in apps if getattr(app, "workspace_slug", None) == workspace_slug]
    return []


def workspace_dashboard_ids(adb, workspace_id: Optional[str]) -> set[str]:
    if not workspace_id or workspace_id == "default":
        return set()
    from app.catalog.models import CatalogWorkspaceBinding, UnifiedCatalogDashboard

    bindings = adb.query(CatalogWorkspaceBinding).all()
    catalog_ids = {
        str(binding.catalog_id)
        for binding in bindings
        if str(getattr(binding, "workspace_id", "")) == str(workspace_id) and getattr(binding, "catalog_id", None)
    }
    if not catalog_ids:
        return set()

    rows = adb.query(UnifiedCatalogDashboard).all()
    allowed: set[str] = set()
    for row in rows:
        dash_id = getattr(row, "dashboard_id", None)
        schema = getattr(row, "schema", None)
        catalog_id = getattr(schema, "catalog_id", None) if schema is not None else getattr(row, "catalog_id", None)
        if dash_id and catalog_id and str(catalog_id) in catalog_ids:
            allowed.add(str(dash_id))
    return allowed


def workspace_dashboards(adb, workspace_id: Optional[str]):
    from app.models.dashboard import Dashboard

    allowed = workspace_dashboard_ids(adb, workspace_id)
    if not allowed:
        return []
    rows = adb.query(Dashboard).order_by(Dashboard.created_at.desc()).all()
    return [row for row in rows if str(row.id) in allowed]


def _field(item: Any, name: str):
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def visible_sections(sections, app_ids: set[str], dashboard_ids: set[str]) -> list[dict]:
    """Drop apps and dashboards that are not in this workspace. Keep external links."""
    kept_sections = []
    for section in sections or []:
        raw_items = _field(section, "items") or []
        kept_items = []
        for item in raw_items:
            kind = _field(item, "type")
            target = str(_field(item, "target_id") or "")
            if kind == "external_link" or (kind == "app" and target in app_ids) or (kind == "dashboard" and target in dashboard_ids):
                kept_items.append(item if isinstance(item, dict) else item.dict())
        kept_sections.append({
            "id": _field(section, "id"),
            "title": _field(section, "title"),
            "items": kept_items,
        })
    return kept_sections
