from __future__ import annotations

import asyncio
import copy
import logging
import threading
import uuid
from concurrent.futures import Future
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.nova.services.tooling import BaseNovaTool, NovaToolResult

logger = logging.getLogger(__name__)


# ── Async helper (mirrors notebook_tools.run_async) ───────────────────────────

def _run_async(coro):
    """Run an async coroutine synchronously, even if a loop is already running."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        future: Future = Future()

        def _run():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(coro)
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
            finally:
                new_loop.close()

        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return future.result()
    else:
        return loop.run_until_complete(coro)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_account_db():
    from app.database import AccountSessionLocal
    return AccountSessionLocal()


def _get_system_db():
    from app.database import SystemSessionLocal
    return SystemSessionLocal()


SNAKE_TO_CAMEL_CHART_CONFIG_MAP = {
    "chart_type": "chartType",
    "dataset_id": "datasetId",
    "x_field": "xField",
    "y_fields": "yFields",
    "color_field": "colorField",
    "size_field": "sizeField",
    "show_gridlines": "showGridlines",
    "show_value_labels": "showValueLabels",
    "value_label_field": "valueLabelField",
    "tooltip_fields": "tooltipFields",
    "line_thickness": "lineThickness",
    "facet_field": "facetField",
    "facet_rows": "facetRows",
    "facet_cols": "facetCols",
    "y2_fields": "y2Fields",
    "comparison_field": "comparisonField",
    "show_sparkline": "showSparkline",
    "conditional_formatting": "conditionalFormatting",
    "lat_field": "latField",
    "lon_field": "lonField",
    "geo_field": "geoField",
    "geo_level": "geoLevel",
}


def _normalize_chart_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        return {}
    normalized = {}
    for k, v in cfg.items():
        if v is None:
            continue
        camel_k = SNAKE_TO_CAMEL_CHART_CONFIG_MAP.get(k, k)
        normalized[camel_k] = v

    for snake_key, camel_key in SNAKE_TO_CAMEL_CHART_CONFIG_MAP.items():
        if snake_key in normalized and camel_key in normalized and snake_key != camel_key:
            normalized.pop(snake_key, None)

    return normalized


def _workspace_id_from_context(context: dict[str, Any]) -> str | None:
    return context.get("workspace_id") or context.get("workspaceId")


def _warehouse_id_from_context(context: dict[str, Any]) -> str | None:
    return context.get("warehouse_id") or context.get("warehouseId")


# ── List Dashboards ────────────────────────────────────────────────────────────

class ListDashboardsTool(BaseNovaTool):
    key = "list_dashboards"
    description = (
        "List all dashboards accessible in this workspace. "
        "Returns id, name, isDraft, page count, and last updated timestamp."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "include_draft": {
                "type": "boolean",
                "description": "Whether to include draft dashboards. Defaults to true.",
                "default": True,
            },
            "name_filter": {
                "type": "string",
                "description": "Optional substring to filter dashboard names (case-insensitive).",
            },
        },
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        include_draft = bool(arguments.get("include_draft", True))
        name_filter = str(arguments.get("name_filter") or "").lower()

        db = _get_account_db()
        try:
            query = db.query(Dashboard).order_by(Dashboard.updated_at.desc())
            dashboards = query.all()

            results = []
            for d in dashboards:
                if not include_draft and d.is_draft:
                    continue
                if name_filter and name_filter not in (d.name or "").lower():
                    continue
                results.append({
                    "id": d.id,
                    "name": d.name,
                    "isDraft": d.is_draft,
                    "pageCount": len(d.pages or []),
                    "datasetCount": len(d.datasets or []),
                    "widgetCount": len(d.widgets or []),
                    "createdBy": d.created_by,
                    "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
                    "publishedAt": d.published_at.isoformat() if d.published_at else None,
                })

            return NovaToolResult(ok=True, result={"dashboards": results, "count": len(results)})
        except Exception as exc:
            logger.exception("list_dashboards failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Get Dashboard ──────────────────────────────────────────────────────────────

class GetDashboardTool(BaseNovaTool):
    key = "get_dashboard"
    description = (
        "Fetch the full structure of a dashboard by id, including pages, widgets, and datasets. "
        "Use list_dashboards first to discover dashboard ids."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {
                "type": "string",
                "description": "The dashboard UUID to retrieve.",
            },
        },
        "required": ["dashboard_id"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            widgets = copy.deepcopy(d.widgets or [])
            for w in widgets:
                if isinstance(w.get("chartConfig"), dict):
                    w["chartConfig"] = _normalize_chart_config(w["chartConfig"])

            return NovaToolResult(ok=True, result={
                "id": d.id,
                "name": d.name,
                "isDraft": d.is_draft,
                "permissionMode": d.permission_mode,
                "createdBy": d.created_by,
                "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
                "publishedAt": d.published_at.isoformat() if d.published_at else None,
                "pages": d.pages or [],
                "widgets": widgets,
                "datasets": d.datasets or [],
                "settings": d.settings,
            })
        except Exception as exc:
            logger.exception("get_dashboard failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Create Dashboard ───────────────────────────────────────────────────────────

class CreateDashboardTool(BaseNovaTool):
    key = "create_dashboard"
    description = (
        "Create a new blank dashboard with the given name. "
        "A first empty page is created automatically. "
        "Returns the full dashboard object including its id, which you need for subsequent operations."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Human-readable name for the new dashboard.",
            },
            "permission_mode": {
                "type": "string",
                "enum": ["individual", "shared"],
                "default": "individual",
                "description": "Permission mode for the dashboard.",
            },
        },
        "required": ["name"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        name = str(arguments["name"]).strip()
        if not name:
            return NovaToolResult(ok=False, error="name must not be empty")

        permission_mode = str(arguments.get("permission_mode") or "individual")
        if permission_mode not in {"individual", "shared"}:
            permission_mode = "individual"

        actor = context.get("user") or context.get("principal_id") or "agent"
        workspace_id = _workspace_id_from_context(context)

        dash_id = str(uuid.uuid4())
        first_page_id = str(uuid.uuid4())

        db = _get_account_db()
        try:
            d = Dashboard(
                id=dash_id,
                name=name,
                permission_mode=permission_mode,
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

            if workspace_id:
                try:
                    _register_in_catalog(db, workspace_id, dash_id, name, actor)
                except Exception as catalog_exc:
                    logger.warning("Failed to register dashboard in catalog: %s", catalog_exc)

            db.commit()
            db.refresh(d)

            return NovaToolResult(ok=True, result={
                "id": d.id,
                "name": d.name,
                "isDraft": d.is_draft,
                "pages": d.pages,
                "widgets": d.widgets,
                "datasets": d.datasets,
                "message": f"Dashboard '{name}' created successfully. Use add_dataset to add SQL datasets, then add_widget to create charts.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("create_dashboard failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


def _register_in_catalog(db, workspace_id: str, dashboard_id: str, name: str, actor: str | None) -> None:
    """Register a dashboard in the default catalog — mirrors dashboard_routes._register_dashboard_in_default_catalog."""
    from app.catalog.models import (
        UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogDashboard, CatalogWorkspaceBinding,
    )

    binding = (
        db.query(CatalogWorkspaceBinding)
        .filter(CatalogWorkspaceBinding.workspace_id == workspace_id)
        .order_by(CatalogWorkspaceBinding.is_default.desc())
        .first()
    )

    catalog = None
    if binding:
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.id == binding.catalog_id).first()
    if not catalog:
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.all_workspaces == True).first()
    if not catalog:
        return

    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.catalog_id == catalog.id).first()
    if not schema:
        schema = UnifiedCatalogSchema(
            catalog_id=catalog.id,
            name="default",
            created_by=actor or "system",
        )
        db.add(schema)
        db.flush()

    catalog_dashboard = UnifiedCatalogDashboard(
        schema_id=schema.id,
        catalog_name=catalog.name,
        schema_name=schema.name,
        name=name,
        dashboard_id=dashboard_id,
        owner=actor,
        created_by=actor or "system",
        updated_by=actor or "system",
    )
    db.add(catalog_dashboard)
    db.flush()


# ── Update Dashboard ───────────────────────────────────────────────────────────

class UpdateDashboardTool(BaseNovaTool):
    key = "update_dashboard"
    description = (
        "Update a dashboard's name, permission mode, or settings (theme, locale, filter apply mode). "
        "Only pass the fields you want to change."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "The dashboard UUID to update."},
            "name": {"type": "string", "description": "New name for the dashboard."},
            "permission_mode": {
                "type": "string",
                "enum": ["individual", "shared"],
                "description": "New permission mode.",
            },
            "settings": {
                "type": "object",
                "description": "Partial dashboard settings to merge (e.g. theme, locale).",
                "additionalProperties": True,
            },
        },
        "required": ["dashboard_id"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            if "name" in arguments and arguments["name"]:
                d.name = str(arguments["name"]).strip()
            if "permission_mode" in arguments and arguments["permission_mode"]:
                d.permission_mode = str(arguments["permission_mode"])
            if "settings" in arguments and isinstance(arguments["settings"], dict):
                existing = d.settings or {}
                d.settings = {**existing, **arguments["settings"]}
                flag_modified(d, "settings")

            db.commit()
            db.refresh(d)
            return NovaToolResult(ok=True, result={
                "id": d.id,
                "name": d.name,
                "isDraft": d.is_draft,
                "settings": d.settings,
                "message": "Dashboard updated successfully.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("update_dashboard failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Add Dataset ────────────────────────────────────────────────────────────────

class AddDatasetTool(BaseNovaTool):
    key = "add_dataset"
    description = (
        "Add a SQL dataset to a dashboard. The SQL should be a valid SELECT query. "
        "Use run_query first to validate the SQL and preview the columns before adding. "
        "Returns the new dataset id which you need when adding widgets."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "Dashboard UUID to add the dataset to."},
            "name": {"type": "string", "description": "Human-readable name for the dataset."},
            "sql": {"type": "string", "description": "SELECT SQL query for this dataset."},
            "params": {
                "type": "array",
                "description": "Optional template parameters embedded in the SQL as :keyword.",
                "items": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "type": {"type": "string", "enum": ["string", "date", "datetime", "decimal", "integer"]},
                        "displayName": {"type": "string"},
                        "defaultValue": {"type": "string"},
                    },
                    "required": ["keyword", "type"],
                },
                "default": [],
            },
        },
        "required": ["dashboard_id", "name", "sql"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        name = str(arguments["name"]).strip()
        sql = str(arguments["sql"]).strip()
        params = arguments.get("params") or []

        if not sql:
            return NovaToolResult(ok=False, error="sql must not be empty")
        if not name:
            return NovaToolResult(ok=False, error="name must not be empty")

        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            dataset_id = str(uuid.uuid4())
            new_dataset = {
                "id": dataset_id,
                "dashboardId": dashboard_id,
                "name": name,
                "sql": sql,
                "params": params if isinstance(params, list) else [],
                "schema": [],
            }

            datasets = copy.deepcopy(d.datasets or [])
            datasets.append(new_dataset)
            d.datasets = datasets
            flag_modified(d, "datasets")
            db.commit()
            db.refresh(d)

            return NovaToolResult(ok=True, result={
                "datasetId": dataset_id,
                "name": name,
                "message": f"Dataset '{name}' added to dashboard. Use add_widget to wire it to a chart.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("add_dataset failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Update Dataset ─────────────────────────────────────────────────────────────

class UpdateDatasetTool(BaseNovaTool):
    key = "update_dataset"
    description = (
        "Update an existing dataset's name or SQL on a dashboard. "
        "Only pass the fields you want to change."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "Dashboard UUID that owns the dataset."},
            "dataset_id": {"type": "string", "description": "Dataset UUID to update."},
            "name": {"type": "string", "description": "New name for the dataset."},
            "sql": {"type": "string", "description": "New SELECT SQL query."},
        },
        "required": ["dashboard_id", "dataset_id"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        dataset_id = str(arguments["dataset_id"])

        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            datasets = copy.deepcopy(d.datasets or [])
            target = next((ds for ds in datasets if ds.get("id") == dataset_id), None)
            if target is None:
                return NovaToolResult(ok=False, error=f"Dataset '{dataset_id}' not found in dashboard")

            if "name" in arguments and arguments["name"]:
                target["name"] = str(arguments["name"]).strip()
            if "sql" in arguments and arguments["sql"]:
                target["sql"] = str(arguments["sql"]).strip()
                target["schema"] = []  # reset schema cache when SQL changes

            d.datasets = datasets
            flag_modified(d, "datasets")
            db.commit()
            return NovaToolResult(ok=True, result={
                "datasetId": dataset_id,
                "name": target.get("name"),
                "message": "Dataset updated successfully.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("update_dataset failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Add Widget ─────────────────────────────────────────────────────────────────

class AddWidgetTool(BaseNovaTool):
    key = "add_widget"
    description = (
        "Add a chart, text, or filter widget to a dashboard page. "
        "For chart widgets, specify chartConfig with chartType, datasetId, xField, and yFields. "
        "The gridItem controls size/position on the page grid (12-column layout, rows ≈ 150px each)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "Dashboard UUID."},
            "page_id": {"type": "string", "description": "Page UUID to add the widget to. Use get_dashboard to find page ids."},
            "widget_type": {
                "type": "string",
                "enum": ["chart", "text", "filter", "html", "image"],
                "description": "Type of widget to add.",
            },
            "title": {"type": "string", "description": "Optional widget title shown in the header."},
            "chart_config": {
                "type": "object",
                "description": (
                    "Chart configuration (required for widget_type=chart). "
                    "Properties: chartType (bar|line|area|pie|scatter|table|counter|histogram|heatmap|...), "
                    "datasetId, xField, yFields (array), colorField, sizeField, layout (stack|group|100stack)."
                ),
                "additionalProperties": True,
            },
            "content": {
                "type": "string",
                "description": "Text/HTML content for text or html widget types.",
            },
            "grid_item": {
                "type": "object",
                "description": (
                    "Grid position and size. Fields: x (0–11), y (row number), w (width in columns 1–12), h (height in rows). "
                    "Defaults to a 6×4 block at position (0, 0) if omitted."
                ),
                "properties": {
                    "x": {"type": "integer", "minimum": 0, "maximum": 11},
                    "y": {"type": "integer", "minimum": 0},
                    "w": {"type": "integer", "minimum": 1, "maximum": 12},
                    "h": {"type": "integer", "minimum": 1},
                },
            },
        },
        "required": ["dashboard_id", "page_id", "widget_type"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        page_id = str(arguments["page_id"])
        widget_type = str(arguments["widget_type"])

        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            pages = d.pages or []
            page = next((p for p in pages if p.get("id") == page_id), None)
            if page is None:
                return NovaToolResult(ok=False, error=f"Page '{page_id}' not found in dashboard")

            widget_id = str(uuid.uuid4())

            # Build grid item — auto-stack below existing widgets if no position given
            raw_grid = arguments.get("grid_item") or {}
            existing_widgets_on_page = [w for w in (d.widgets or []) if w.get("pageId") == page_id]
            max_y = max((w.get("gridItem", {}).get("y", 0) + w.get("gridItem", {}).get("h", 4)
                         for w in existing_widgets_on_page), default=0)
            grid_item = {
                "i": widget_id,
                "x": int(raw_grid.get("x", 0)),
                "y": int(raw_grid.get("y", max_y)),
                "w": int(raw_grid.get("w", 6)),
                "h": int(raw_grid.get("h", 4)),
            }

            new_widget: dict[str, Any] = {
                "id": widget_id,
                "pageId": page_id,
                "widgetType": widget_type,
                "gridItem": grid_item,
            }

            if arguments.get("title"):
                new_widget["title"] = str(arguments["title"])

            if widget_type == "chart" and isinstance(arguments.get("chart_config"), dict):
                new_widget["chartConfig"] = _normalize_chart_config(arguments["chart_config"])

            if widget_type in {"text", "html", "image"} and arguments.get("content"):
                new_widget["content"] = str(arguments["content"])

            widgets = copy.deepcopy(d.widgets or [])
            widgets.append(new_widget)
            d.widgets = widgets
            flag_modified(d, "widgets")

            # Also update page layout
            pages = copy.deepcopy(d.pages or [])
            page = next((p for p in pages if p.get("id") == page_id), None)
            if page is not None:
                layout = list(page.get("layout") or [])
                layout.append(grid_item)
                page["layout"] = layout
                d.pages = pages
                flag_modified(d, "pages")

            db.commit()
            return NovaToolResult(ok=True, result={
                "widgetId": widget_id,
                "widgetType": widget_type,
                "gridItem": grid_item,
                "chartConfig": new_widget.get("chartConfig"),
                "message": f"Widget '{widget_type}' added to page. Use update_widget to refine chart config.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("add_widget failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Update Widget ──────────────────────────────────────────────────────────────

class UpdateWidgetTool(BaseNovaTool):
    key = "update_widget"
    description = (
        "Update a widget's title, chart configuration, or content. "
        "Only pass the fields you want to change. "
        "For chart_config, pass chartType, xField, yFields (array), datasetId, etc."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "Dashboard UUID."},
            "widget_id": {"type": "string", "description": "Widget UUID to update."},
            "title": {"type": "string", "description": "New title for the widget."},
            "chart_config": {
                "type": "object",
                "description": "Partial chart config. Standard fields: chartType (bar|line|area|pie|scatter|table|counter), xField, yFields (array), datasetId.",
                "additionalProperties": True,
            },
            "content": {
                "type": "string",
                "description": "New text/HTML content for text or html widgets.",
            },
            "grid_item": {
                "type": "object",
                "description": "New grid position/size. Partial patch — only changed fields needed.",
                "additionalProperties": True,
            },
        },
        "required": ["dashboard_id", "widget_id"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        widget_id = str(arguments["widget_id"])

        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            widgets = copy.deepcopy(d.widgets or [])
            target = next((w for w in widgets if w.get("id") == widget_id), None)
            if target is None:
                return NovaToolResult(ok=False, error=f"Widget '{widget_id}' not found in dashboard")

            if "title" in arguments:
                target["title"] = str(arguments["title"])
            if "content" in arguments:
                target["content"] = str(arguments["content"])
            if isinstance(arguments.get("chart_config"), dict):
                existing_cfg = _normalize_chart_config(target.get("chartConfig") or {})
                patch_cfg = _normalize_chart_config(arguments["chart_config"])
                target["chartConfig"] = {**existing_cfg, **patch_cfg}
            if isinstance(arguments.get("grid_item"), dict):
                existing_grid = target.get("gridItem") or {}
                target["gridItem"] = {**existing_grid, **arguments["grid_item"], "i": widget_id}

            d.widgets = widgets
            flag_modified(d, "widgets")
            db.commit()
            return NovaToolResult(ok=True, result={
                "widgetId": widget_id,
                "chartConfig": target.get("chartConfig"),
                "message": "Widget updated successfully.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("update_widget failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Run Query ──────────────────────────────────────────────────────────────────

class RunQueryTool(BaseNovaTool):
    key = "run_query"
    description = (
        "Execute a read-only SELECT SQL query through the SQL warehouse and return the column names "
        "and a sample of rows (up to 100). Use this to validate SQL and discover column names before "
        "wiring a dataset to a widget. Never use for data-modifying statements."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "The SELECT SQL to execute."},
            "max_rows": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 20,
                "description": "Maximum number of rows to return (1–100).",
            },
            "warehouse_id": {
                "type": "string",
                "description": "Optional warehouse UUID to use. Defaults to the first running warehouse.",
            },
        },
        "required": ["sql"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        sql = str(arguments["sql"]).strip()
        if not sql:
            return NovaToolResult(ok=False, error="sql must not be empty")

        max_rows = min(max(int(arguments.get("max_rows", 20)), 1), 100)
        warehouse_id = str(arguments["warehouse_id"]) if arguments.get("warehouse_id") else None
        workspace_id = _workspace_id_from_context(context)

        # Reject obviously mutating statements
        first_token = sql.lstrip().split()[0].upper() if sql.strip() else ""
        if first_token not in {"SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"}:
            return NovaToolResult(ok=False, error="Only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN queries are permitted.")

        system_db = _get_system_db()
        try:
            from app.sql_warehouse.warehouse.manager import get_warehouse_by_id, list_warehouses
            from app.sql_warehouse.query.executor import QueryExecutor

            if warehouse_id:
                warehouse = get_warehouse_by_id(system_db, warehouse_id, workspace_id=workspace_id)
                if warehouse is None:
                    return NovaToolResult(ok=False, error=f"Warehouse '{warehouse_id}' not found")
            else:
                warehouses = list_warehouses(system_db, workspace_id=workspace_id)
                warehouse = next((w for w in warehouses if w.status == "running"), None)
                if warehouse is None:
                    return NovaToolResult(
                        ok=False,
                        error="No running SQL warehouse available. Start a warehouse first.",
                    )

            executor = QueryExecutor(system_db)
            result = _run_async(
                executor.run(
                    warehouse=warehouse,
                    sql=sql,
                    user_id="agent",
                    session_id=None,
                    max_rows=max_rows,
                )
            )

            return NovaToolResult(ok=True, result={
                "columns": result["columns"],
                "rows": result["rows"][:max_rows],
                "rowCount": len(result["rows"]),
                "executionMs": result.get("execution_time_ms", result.get("duration_ms", 0)),
            })
        except Exception as exc:
            logger.exception("run_query failed")
            return NovaToolResult(ok=False, error=f"Query error: {exc}")
        finally:
            system_db.close()


# ── Publish Dashboard ──────────────────────────────────────────────────────────

class PublishDashboardTool(BaseNovaTool):
    key = "publish_dashboard"
    description = (
        "Publish a dashboard draft, making it visible to consumers. "
        "Sets is_draft to false and records the published_at timestamp."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "Dashboard UUID to publish."},
        },
        "required": ["dashboard_id"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from datetime import datetime, timezone
        from app.models.dashboard import Dashboard

        dashboard_id = str(arguments["dashboard_id"])
        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            d.is_draft = False
            d.published_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(d)

            return NovaToolResult(ok=True, result={
                "id": d.id,
                "name": d.name,
                "isDraft": d.is_draft,
                "publishedAt": d.published_at.isoformat(),
                "message": f"Dashboard '{d.name}' published successfully.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("publish_dashboard failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


# ── Tool registry ──────────────────────────────────────────────────────────────

DASHBOARD_NOVA_TOOLS: list[BaseNovaTool] = [
    ListDashboardsTool(),
    GetDashboardTool(),
    CreateDashboardTool(),
    UpdateDashboardTool(),
    AddDatasetTool(),
    UpdateDatasetTool(),
    AddWidgetTool(),
    UpdateWidgetTool(),
    RunQueryTool(),
    PublishDashboardTool(),
]
