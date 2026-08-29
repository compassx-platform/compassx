"""Dashboard Change Handler — Encapsulates change capture, serialization, and rollback for Dashboards."""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from app.agents.services.agent.change_capture.base import BaseAssetChangeHandler

logger = logging.getLogger(__name__)

READ_ONLY_DASH_OPERATIONS = {
    "describe_widget",
    "list_dashboards",
    "get_dashboard",
    "run_query",
}

MUTATING_DASH_OPERATIONS = {
    "create_dashboard",
    "update_dashboard",
    "add_dataset",
    "update_dataset",
    "add_widget",
    "update_widget",
    "publish_dashboard",
}


class DashboardChangeHandler(BaseAssetChangeHandler):
    """Handler managing Dashboard asset changes (SRP)."""

    @property
    def object_type(self) -> str:
        return "dashboard"

    def supports_tool(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        t_lower = tool_name.lower()
        if t_lower == "dashboard_manager" or "dashboard" in t_lower:
            return True
        if operation and (operation in MUTATING_DASH_OPERATIONS or operation in READ_ONLY_DASH_OPERATIONS):
            return True
        return False

    def is_mutating(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        op = (operation or (payload.get("operation") if isinstance(payload, dict) else None) or tool_name).lower()
        if op in READ_ONLY_DASH_OPERATIONS:
            return False
        if op in MUTATING_DASH_OPERATIONS or "create" in op or "update" in op or "add" in op or "publish" in op:
            return True
        return False

    def resolve_full_name(
        self,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
        goal: str | None = None,
    ) -> str | None:
        pld = payload or {}
        res_data = result.get("data") if isinstance(result.get("data"), dict) else result

        # 1. Check explicit catalog coordinates
        cat = pld.get("catalog_name") or res_data.get("catalog_name")
        sch = pld.get("schema_name") or res_data.get("schema_name")
        nm = pld.get("name") or pld.get("dashboard_name") or res_data.get("name") or res_data.get("dashboard_name")
        if cat and sch and nm:
            return f"{cat}.{sch}.{nm}"

        # 2. Look up dashboard in database by ID
        dash_id = (
            pld.get("dashboard_id")
            or pld.get("dashboardId")
            or res_data.get("id")
            or res_data.get("dashboard_id")
            or result.get("resource_id")
        )
        if dash_id:
            try:
                from app.database import AccountSessionLocal
                from app.catalog.models import UnifiedCatalogDashboard
                from app.models.dashboard import Dashboard

                with AccountSessionLocal() as account_db:
                    uc_dash = account_db.query(UnifiedCatalogDashboard).filter(
                        (UnifiedCatalogDashboard.dashboard_id == str(dash_id)) | (UnifiedCatalogDashboard.id == str(dash_id))
                    ).first()
                    if uc_dash and uc_dash.full_name:
                        return uc_dash.full_name

                    d = account_db.query(Dashboard).filter(Dashboard.id == str(dash_id)).first()
                    if d and d.name:
                        slug = re.sub(r"[^a-zA-Z0-9_]", "_", d.name.strip()).strip("_").lower()
                        return f"workspace.dashboards.{slug}"
            except Exception as exc:
                logger.debug("Error resolving dashboard full_name from DB: %s", exc)

        # 3. Fallback to goal slug
        if goal:
            goal_slug = re.sub(r"[^a-zA-Z0-9_]", "_", goal[:30].strip()).strip("_").lower()
            return f"workspace.dashboards.{goal_slug or 'dashboard'}"

        return "workspace.dashboards.analytics_dashboard"

    def serialize_current_state(
        self,
        full_name: str,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str | None:
        pld = payload or {}
        res_data = result.get("data") if isinstance(result.get("data"), dict) else result

        dash_id = (
            pld.get("dashboard_id")
            or pld.get("dashboardId")
            or res_data.get("id")
            or res_data.get("dashboard_id")
            or result.get("resource_id")
        )

        try:
            from app.database import AccountSessionLocal
            from app.models.dashboard import Dashboard
            from app.catalog.models import UnifiedCatalogDashboard

            with AccountSessionLocal() as account_db:
                d = None
                if dash_id:
                    d = account_db.query(Dashboard).filter(Dashboard.id == str(dash_id)).first()

                if not d and full_name:
                    dot_parts = full_name.split(".")
                    if len(dot_parts) == 3:
                        uc_dash = account_db.query(UnifiedCatalogDashboard).filter(
                            UnifiedCatalogDashboard.catalog_name == dot_parts[0],
                            UnifiedCatalogDashboard.schema_name == dot_parts[1],
                            UnifiedCatalogDashboard.name == dot_parts[2],
                        ).first()
                        if uc_dash:
                            d = account_db.query(Dashboard).filter(
                                (Dashboard.id == uc_dash.dashboard_id) | (Dashboard.id == uc_dash.id)
                            ).first()
                    if not d:
                        last_part = dot_parts[-1]
                        d = account_db.query(Dashboard).filter(
                            (Dashboard.name == last_part) | (Dashboard.name == full_name) | (Dashboard.id == full_name)
                        ).first()

                if d:
                    dash_spec = {
                        "name": d.name,
                        "datasets": [
                            {
                                "name": ds.get("name"),
                                "query": ds.get("query"),
                                "datasetId": ds.get("datasetId") or ds.get("id"),
                            }
                            for ds in (d.datasets or [])
                        ],
                        "widgets": [
                            {
                                "title": w.get("title"),
                                "widgetType": w.get("widgetType"),
                                "chartConfig": w.get("chartConfig"),
                                "gridItem": w.get("gridItem"),
                            }
                            for w in (d.widgets or [])
                        ],
                        "pages": [
                            {"name": p.get("name"), "layout": p.get("layout")}
                            for p in (d.pages or [])
                        ],
                    }
                    if d.settings:
                        dash_spec["settings"] = d.settings
                    return json.dumps(dash_spec, indent=2)
        except Exception as exc:
            logger.warning("Failed serializing dashboard current state: %s", exc)

        # Fallback to result data if DB lookup unavailable
        if isinstance(res_data, dict) and ("widgets" in res_data or "datasets" in res_data or "pages" in res_data):
            return json.dumps(res_data, indent=2)

        return None

    def revert(self, full_name: str, before_content: str | None) -> bool:
        try:
            from app.database import AccountSessionLocal
            from app.models.dashboard import Dashboard
            from app.catalog.models import UnifiedCatalogDashboard

            with AccountSessionLocal() as account_db:
                d = None
                dot_parts = full_name.split(".")
                if len(dot_parts) == 3:
                    uc_dash = account_db.query(UnifiedCatalogDashboard).filter(
                        UnifiedCatalogDashboard.catalog_name == dot_parts[0],
                        UnifiedCatalogDashboard.schema_name == dot_parts[1],
                        UnifiedCatalogDashboard.name == dot_parts[2],
                    ).first()
                    if uc_dash:
                        d = account_db.query(Dashboard).filter(
                            (Dashboard.id == uc_dash.dashboard_id) | (Dashboard.id == uc_dash.id)
                        ).first()

                if not d:
                    last_part = dot_parts[-1]
                    d = account_db.query(Dashboard).filter(
                        (Dashboard.name == last_part) | (Dashboard.name == full_name) | (Dashboard.id == full_name)
                    ).first()

                if not d:
                    logger.warning("Revert target dashboard not found for: %s", full_name)
                    return False

                if before_content:
                    try:
                        bdata = json.loads(before_content)
                        if isinstance(bdata, dict):
                            if "name" in bdata and bdata["name"]:
                                d.name = str(bdata["name"])
                            if "pages" in bdata and isinstance(bdata["pages"], list):
                                d.pages = copy.deepcopy(bdata["pages"])
                                flag_modified(d, "pages")
                            if "widgets" in bdata and isinstance(bdata["widgets"], list):
                                d.widgets = copy.deepcopy(bdata["widgets"])
                                flag_modified(d, "widgets")
                            if "datasets" in bdata and isinstance(bdata["datasets"], list):
                                d.datasets = copy.deepcopy(bdata["datasets"])
                                flag_modified(d, "datasets")
                            if "settings" in bdata:
                                d.settings = copy.deepcopy(bdata["settings"])
                                flag_modified(d, "settings")
                            account_db.commit()
                            logger.info("Successfully reverted dashboard %s to before_content", full_name)
                            return True
                    except Exception as parse_err:
                        logger.warning("Failed parsing dashboard before_content for revert: %s", parse_err)
                        return False
                else:
                    # Undo initial creation: remove from catalog and delete dashboard
                    dash_id = d.id
                    uc_dash = account_db.query(UnifiedCatalogDashboard).filter(
                        (UnifiedCatalogDashboard.dashboard_id == dash_id) | (UnifiedCatalogDashboard.id == dash_id)
                    ).first()
                    if uc_dash:
                        account_db.delete(uc_dash)
                    account_db.delete(d)
                    account_db.commit()
                    logger.info("Successfully reverted initial creation of dashboard %s", full_name)
                    return True
        except Exception as exc:
            logger.exception("Failed reverting dashboard %s: %s", full_name, exc)
            return False
        return False
