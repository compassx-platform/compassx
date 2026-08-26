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
    "title_row_bg": "titleRowBg",
    "title_row_color": "titleRowColor",
    "title_row_background_color": "titleRowBg",
    "title_row_text_color": "titleRowColor",
    "header_bg": "titleRowBg",
    "header_color": "titleRowColor",
    "header_background_color": "titleRowBg",
    "header_text_color": "titleRowColor",
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


def _workspace_id_from_context(context: dict[str, Any] | None) -> str | None:

    if not isinstance(context, dict):
        return None
    return context.get("workspace_id") or context.get("workspaceId")


def _warehouse_id_from_context(context: dict[str, Any] | None) -> str | None:
    if not isinstance(context, dict):
        return None
    return context.get("warehouse_id") or context.get("warehouseId")


VALID_WIDGET_TYPES = ["chart", "text", "filter", "html", "image"]


VALID_CHART_TYPES = [
    "bar", "line", "area", "pie", "counter", "table", "pivot",
    "waterfall", "scatter", "funnel", "heatmap", "box", "bubble",
    "combo", "sankey", "choropleth", "point_map", "cohort", "histogram"
]

WIDGET_SPECS_CATALOG: dict[str, dict[str, Any]] = {
    "counter": {
        "chartType": "counter",
        "name": "Metric Card / Single Stat",
        "description": "Displays a single primary KPI metric value with optional secondary comparison (target, previous period, or sparkline trend).",
        "requiredFields": ["datasetId", "yFields (1 measure column)"],
        "optionalFields": {
            "title": "Widget title shown in header",
            "comparisonField": "Secondary column to compare against",
            "showSparkline": "boolean (renders mini trendline if date ordered rows available)",
            "conditionalFormatting": "[{min: 90, max: 100, color: '#22c55e'}, {max: 89, color: '#ef4444'}]",
            "numberFormat": "{type: 'number'|'currency'|'percent', abbreviation: 'compact'|'none', currencySymbol: '₹'|'$', decimals: 2}"
        },
        "example": {
            "widget_type": "chart",
            "title": "Total Generation MWh",
            "chart_config": {
                "chartType": "counter",
                "datasetId": "DATASET_UUID",
                "yFields": ["total_generation_mwh"],
                "numberFormat": {"type": "number", "abbreviation": "compact", "decimals": 2}
            }
        }
    },
    "bar": {
        "chartType": "bar",
        "name": "Bar / Column Chart",
        "description": "Vertical or horizontal bars comparing discrete categories across one or more numeric metrics.",
        "requiredFields": ["datasetId", "xField (dimension)", "yFields (array of measure columns)"],
        "optionalFields": {
            "colorField": "Dimension column for grouped / multi-color series",
            "layout": "'group' (default side-by-side) | 'stack' (stacked bars) | '100stack' (percentage stack)",
            "facetField": "Dimension column to split into grid sub-charts",
            "showValueLabels": "boolean (display exact numbers on top of bars)",
            "showGridlines": "boolean"
        },
        "example": {
            "widget_type": "chart",
            "title": "Capacity by Site (AC vs DC MW)",
            "chart_config": {
                "chartType": "bar",
                "datasetId": "DATASET_UUID",
                "xField": "site",
                "yFields": ["ac_capacity_mw", "dc_capacity_mwp"],
                "layout": "group",
                "showValueLabels": True,
                "showGridlines": True
            }
        }
    },
    "line": {
        "chartType": "line",
        "name": "Time-Series Trend Line Chart",
        "description": "Continuous multi-line or single-line trend charts across dates, timestamps, or sequential values.",
        "requiredFields": ["datasetId", "xField (date/time/sequence)", "yFields (array of measures)"],
        "optionalFields": {
            "colorField": "Dimension to produce one line per category",
            "lineThickness": "integer (1 to 5)",
            "showGridlines": "boolean",
            "annotations": "[{axis: 'y', value: 100.0, label: 'Target Line', color: '#ef4444'}]",
            "aiForecast": "boolean"
        },
        "example": {
            "widget_type": "chart",
            "title": "Daily Actual vs Budget Energy",
            "chart_config": {
                "chartType": "line",
                "datasetId": "DATASET_UUID",
                "xField": "report_date",
                "yFields": ["me_mwh", "be_mwh"],
                "showGridlines": True
            }
        }
    },
    "table": {
        "chartType": "table",
        "name": "Interactive Data Table",
        "description": "Tabular grid showing all or selected dataset columns with search, sorting, and pagination.",
        "requiredFields": ["datasetId"],
        "optionalFields": {
            "pageSize": "integer (default 10 or 25)",
            "showSearch": "boolean (default True)",
            "wrapText": "boolean",
            "showRowNumbers": "boolean",
            "titleRowBg": "string (hex/CSS color for table header/title row background, e.g. '#1e293b' or '#f1f5f9')",
            "titleRowColor": "string (hex/CSS color for table header/title row text, e.g. '#ffffff')",
        },
        "example": {
            "widget_type": "chart",
            "title": "Site Operations Master Log",
            "chart_config": {
                "chartType": "table",
                "datasetId": "DATASET_UUID",
                "pageSize": 25,
                "showSearch": True,
                "titleRowBg": "#f1f5f9"
            }
        }
    },
    "pie": {
        "chartType": "pie",
        "name": "Pie / Donut Breakdown Chart",
        "description": "Circular slice breakdown showing proportional contribution of categories to a total.",
        "requiredFields": ["datasetId", "xField (slice category)", "yFields (1 slice measure)"],
        "optionalFields": {
            "showValueLabels": "boolean (show percentage / values on slices)"
        },
        "example": {
            "widget_type": "chart",
            "title": "Revenue Loss by Equipment Type",
            "chart_config": {
                "chartType": "pie",
                "datasetId": "DATASET_UUID",
                "xField": "equipment_type",
                "yFields": ["revenue_loss_mn"],
                "showValueLabels": True
            }
        }
    },
    "combo": {
        "chartType": "combo",
        "name": "Dual-Axis Combo Chart (Bar + Line)",
        "description": "Combines bars on primary left Y-axis with lines on secondary right Y2-axis for comparing measures on different scales.",
        "requiredFields": ["datasetId", "xField", "yFields (primary left axis measures)", "y2Fields (secondary right axis measures)"],
        "optionalFields": {
            "showGridlines": "boolean",
            "showValueLabels": "boolean"
        },
        "example": {
            "widget_type": "chart",
            "title": "Energy Generation (MWh) vs Availability (%)",
            "chart_config": {
                "chartType": "combo",
                "datasetId": "DATASET_UUID",
                "xField": "report_date",
                "yFields": ["actual_energy_mwh"],
                "y2Fields": ["plant_availability_pct"],
                "showGridlines": True
            }
        }
    },
    "waterfall": {
        "chartType": "waterfall",
        "name": "Waterfall Variance Chart",
        "description": "Sequential bar chart showing cumulative positive and negative steps from initial baseline to final total.",
        "requiredFields": ["datasetId", "xField (step category)", "yFields (step variance delta)"],
        "optionalFields": {
            "showValueLabels": "boolean"
        },
        "example": {
            "widget_type": "chart",
            "title": "Energy Generation Loss Waterfall (MWh)",
            "chart_config": {
                "chartType": "waterfall",
                "datasetId": "DATASET_UUID",
                "xField": "loss_component",
                "yFields": ["variance_mwh"]
            }
        }
    },
    "pivot": {
        "chartType": "pivot",
        "name": "Multi-Dimensional Pivot Matrix",
        "description": "Aggregated pivot matrix grouping rows and columns across hierarchical dimensions.",
        "requiredFields": ["datasetId", "xField (columns)", "yFields (values)"],
        "optionalFields": {
            "facetField": "Row grouping dimension"
        },
        "example": {
            "widget_type": "chart",
            "title": "Monthly Cleaning Matrix by Site",
            "chart_config": {
                "chartType": "pivot",
                "datasetId": "DATASET_UUID",
                "xField": "cleaning_status",
                "yFields": ["cleaned_modules_count"],
                "facetField": "site"
            }
        }
    }
}


# ── Describe Widget ────────────────────────────────────────────────────────────

class DescribeWidgetTool(BaseNovaTool):
    key = "describe_widget"
    description = (
        "Inspect required fields, optional configurations, and copy-pasteable JSON examples "
        "for any chart widget type (counter, bar, line, table, pie, combo, waterfall, pivot, etc.). "
        "Call this tool to get exact parameter definitions before adding widgets."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": VALID_CHART_TYPES,
                "description": "Specific chart type to inspect (e.g. 'counter', 'bar', 'line', 'table', 'pie', 'combo', 'waterfall', 'pivot'). If omitted, returns list of all supported chart types.",
            },
        },
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        chart_type = (arguments.get("chart_type") or "").strip().lower()
        if not chart_type:
            return NovaToolResult(
                ok=True,
                result={
                    "supportedChartTypes": VALID_CHART_TYPES,
                    "supportedWidgetTypes": VALID_WIDGET_TYPES,
                    "message": "Pass chart_type (e.g. 'counter', 'bar', 'line', 'table', 'combo', 'waterfall') to inspect its full schema and example.",
                },
            )

        spec = WIDGET_SPECS_CATALOG.get(chart_type)
        if spec:
            return NovaToolResult(ok=True, result=spec)

        return NovaToolResult(
            ok=True,
            result={
                "chartType": chart_type,
                "requiredFields": ["datasetId", "xField", "yFields"],
                "optionalFields": {"colorField": "string", "showGridlines": "boolean", "showValueLabels": "boolean"},
                "example": {
                    "widget_type": "chart",
                    "title": f"Sample {chart_type.title()} Chart",
                    "chart_config": {
                        "chartType": chart_type,
                        "datasetId": "DATASET_UUID",
                        "xField": "dimension_column",
                        "yFields": ["measure_column"]
                    }
                }
            },
        )


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
        "Create a new blank dashboard in the required catalog_name and schema_name. "
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
            "catalog_name": {
                "type": "string",
                "description": "Catalog in the current workspace where the dashboard will be registered.",
            },
            "schema_name": {
                "type": "string",
                "description": "Existing schema in the selected catalog where the dashboard will be registered.",
            },
        },
        "required": ["name", "catalog_name", "schema_name"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        from app.models.dashboard import Dashboard

        name = str(arguments["name"]).strip()
        if not name:
            return NovaToolResult(ok=False, error="name must not be empty")

        permission_mode = str(arguments.get("permission_mode") or "individual")
        if permission_mode not in {"individual", "shared"}:
            permission_mode = "individual"

        catalog_name = str(arguments.get("catalog_name") or "").strip()
        schema_name = str(arguments.get("schema_name") or "").strip()
        if not catalog_name or not schema_name:
            return NovaToolResult(
                ok=False,
                error="catalog_name and schema_name are required to create a dashboard",
            )

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

            _register_in_catalog(
                db,
                workspace_id,
                catalog_name,
                schema_name,
                dash_id,
                name,
                actor,
            )

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


def _register_in_catalog(
    db,
    workspace_id: str | None,
    catalog_name: str,
    schema_name: str,
    dashboard_id: str,
    name: str,
    actor: str | None,
) -> None:
    """Register a dashboard in an explicitly selected, workspace-accessible schema."""
    from app.catalog.models import (
        UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogDashboard, CatalogWorkspaceBinding,
    )

    catalog_query = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name)
    if workspace_id:
        catalog_query = catalog_query.outerjoin(CatalogWorkspaceBinding).filter(
            (UnifiedCatalog.all_workspaces == True)
            | (CatalogWorkspaceBinding.workspace_id == workspace_id)
        )
    catalog = catalog_query.first()
    if not catalog:
        raise ValueError(
            f"Catalog '{catalog_name}' was not found or is not accessible in the current workspace"
        )

    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name,
        )
        .first()
    )
    if not schema:
        raise ValueError(
            f"Schema '{catalog_name}.{schema_name}' was not found in the current workspace"
        )

    existing_cd = (
        db.query(UnifiedCatalogDashboard)
        .filter(UnifiedCatalogDashboard.dashboard_id == dashboard_id)
        .first()
    )
    if not existing_cd:
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
    else:
        existing_cd.name = name
        existing_cd.updated_by = actor or "system"
        db.flush()



# ── Update Dashboard ───────────────────────────────────────────────────────────

def _reconcile_widgets_with_pages(
    pages: list[dict[str, Any]],
    current_widgets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep every widget attached to a page after the page list is replaced."""
    widgets = copy.deepcopy(current_widgets)
    valid_page_ids = {page["id"] for page in pages}
    fallback_page_id = pages[0]["id"]

    for widget in widgets:
        if widget.get("pageId") not in valid_page_ids:
            widget["pageId"] = fallback_page_id

    for page in pages:
        page["layout"] = [
            copy.deepcopy(widget["gridItem"])
            for widget in widgets
            if widget.get("pageId") == page["id"] and isinstance(widget.get("gridItem"), dict)
        ]

    return widgets

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
            "pages": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Complete ordered page-name list. Existing page IDs are preserved by name; "
                    "widgets from removed pages are moved to the first resulting page."
                ),
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
            if "pages" in arguments and isinstance(arguments["pages"], list):
                new_pages = []
                existing_pages_by_id = {p.get("id"): p for p in (d.pages or []) if isinstance(p, dict)}
                existing_pages_by_name = {p.get("name"): p for p in (d.pages or []) if isinstance(p, dict)}
                for idx, p in enumerate(arguments["pages"]):
                    if isinstance(p, str):
                        existing_match = existing_pages_by_name.get(p)
                        p_id = existing_match.get("id") if existing_match else str(uuid.uuid4())
                        existing_layout = existing_match.get("layout", []) if existing_match else []
                        new_pages.append({
                            "id": p_id,
                            "dashboardId": d.id,
                            "name": p,
                            "order": idx,
                            "layout": existing_layout,
                        })
                    elif isinstance(p, dict):
                        p_name = p.get("name") or f"Page {idx + 1}"
                        existing_match = (
                            existing_pages_by_id.get(p.get("id"))
                            or existing_pages_by_name.get(p_name)
                        )
                        p_id = p.get("id") or (existing_match.get("id") if existing_match else str(uuid.uuid4()))
                        existing_layout = (
                            p.get("layout")
                            or (existing_match.get("layout", []) if existing_match else [])
                        )
                        new_pages.append({
                            "id": p_id,
                            "dashboardId": d.id,
                            "name": p_name,
                            "order": int(p.get("order", idx)),
                            "layout": existing_layout,
                        })
                if new_pages:
                    widgets = _reconcile_widgets_with_pages(new_pages, d.widgets or [])
                    d.pages = new_pages
                    d.widgets = widgets
                    flag_modified(d, "pages")
                    flag_modified(d, "widgets")


            db.commit()
            db.refresh(d)
            return NovaToolResult(ok=True, result={
                "id": d.id,
                "name": d.name,
                "isDraft": d.is_draft,
                "pages": d.pages,
                "settings": d.settings,
                "message": "Dashboard updated successfully.",
            })
        except Exception as exc:
            db.rollback()
            logger.exception("update_dashboard failed")
            return NovaToolResult(ok=False, error=str(exc))
        finally:
            db.close()


def _validate_sql_query(sql: str, context: dict[str, Any] | None = None) -> tuple[bool, list[str], str | None]:

    workspace_id = _workspace_id_from_context(context)
    warehouse_id = _warehouse_id_from_context(context)

    first_token = sql.lstrip().split()[0].upper() if sql.strip() else ""
    if first_token not in {"SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"}:
        return False, [], "Only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN queries are permitted."

    dry_run_sql = f"SELECT * FROM ({sql}) _dry_run_q LIMIT 0"
    system_db = _get_system_db()
    try:
        from app.sql_warehouse.warehouse.manager import get_warehouse_by_id, list_warehouses
        from app.sql_warehouse.query.executor import QueryExecutor

        if warehouse_id:
            wh = get_warehouse_by_id(system_db, warehouse_id)
            warehouse = wh
        else:
            warehouses = list_warehouses(system_db, workspace_id=workspace_id)
            running = [w for w in warehouses if getattr(w, "status", None) and str(w.status).lower() == "running"]
            warehouse = running[0] if running else (warehouses[0] if warehouses else None)

        if not warehouse:
            return True, [], None

        executor = QueryExecutor(system_db)
        result = _run_async(
            executor.run(
                warehouse=warehouse,
                sql=dry_run_sql,
                user_id="agent",
                session_id=None,
                max_rows=1,
            )
        )
        return True, result.get("columns", []), None
    except Exception as exc:
        err_msg = str(exc)
        return False, [], f"SQL ValidationError: {err_msg}"
    finally:
        system_db.close()


# ── Add Dataset ────────────────────────────────────────────────────────────────

class AddDatasetTool(BaseNovaTool):

    key = "add_dataset"
    description = (
        "Add a new named SQL dataset to a dashboard. "
        "The SQL query is executed through the SQL warehouse and its columns are bound to chart widgets."
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

        # Validate SQL against warehouse before persisting
        is_valid, cols, err = _validate_sql_query(sql, context)
        if not is_valid:
            return NovaToolResult(ok=False, error=err)

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
                "schema": [{"name": col, "type": "unknown"} for col in cols],
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
                "columns": cols,
                "message": f"Dataset '{name}' added to dashboard. Verified columns: {cols}. Use add_widget to wire it to a chart.",
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

            cols = []
            if "sql" in arguments and arguments["sql"]:
                new_sql = str(arguments["sql"]).strip()
                is_valid, cols, err = _validate_sql_query(new_sql, context)
                if not is_valid:
                    return NovaToolResult(ok=False, error=err)
                target["sql"] = new_sql
                target["schema"] = [{"name": col, "type": "unknown"} for col in cols]

            if "name" in arguments and arguments["name"]:
                target["name"] = str(arguments["name"]).strip()

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
        "For chart widgets, widget_type MUST be 'chart', and chart_config MUST specify chartType (e.g. 'counter', 'bar', 'line', 'table', 'pie', 'combo', 'waterfall') and a valid datasetId. "
        "Use describe_widget to inspect the exact schema and examples for any chart type. "
        "The gridItem controls size/position on the 12-column grid (x: 0-11, y: row, w: cols 1-12, h: rows 1-12)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "string", "description": "Dashboard UUID."},
            "page_id": {"type": "string", "description": "Page UUID to add the widget to. Use get_dashboard to find page ids."},
            "widget_type": {
                "type": "string",
                "enum": ["chart", "text", "filter", "html", "image"],
                "description": "Type of widget to add. MUST be 'chart' for any data visualization (metric cards, bar charts, trend lines, tables, pie charts, waterfalls).",
            },
            "title": {"type": "string", "description": "Optional widget title shown in the header."},
            "chart_config": {
                "type": "object",
                "description": (
                    "Chart configuration (REQUIRED when widget_type='chart'). "
                    "Fields: chartType (one of: bar, line, area, pie, counter, table, pivot, waterfall, scatter, funnel, heatmap, combo), "
                    "datasetId (REQUIRED, must be an existing dataset on the dashboard), "
                    "xField (dimension column), yFields (array of measure columns), y2Fields (secondary Y axis for combo), "
                    "colorField, showGridlines, showValueLabels, numberFormat, annotations."
                ),
                "properties": {
                    "chartType": {"type": "string", "enum": VALID_CHART_TYPES},
                    "datasetId": {"type": "string", "description": "UUID of the dataset bound to this chart."},
                    "xField": {"type": "string", "description": "Dimension column name for X axis or category breakdown."},
                    "yFields": {"type": "array", "items": {"type": "string"}, "description": "List of measure column names for Y axis."},
                    "y2Fields": {"type": "array", "items": {"type": "string"}, "description": "Secondary Y-axis measure columns (for combo charts)."},
                    "colorField": {"type": "string", "description": "Dimension column to split series by color."},
                    "showGridlines": {"type": "boolean"},
                    "showValueLabels": {"type": "boolean"},
                    "layout": {"type": "string", "enum": ["group", "stack", "100stack"]},
                },
                "required": ["chartType", "datasetId"],
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

        dashboard_id = str(arguments.get("dashboard_id") or "")
        page_id = str(arguments.get("page_id") or "")
        widget_type = str(arguments.get("widget_type") or "").strip().lower()

        if widget_type not in VALID_WIDGET_TYPES:
            return NovaToolResult(
                ok=False,
                error=(
                    f"ValidationError: Invalid widget_type '{widget_type}'. "
                    f"Must be one of: {VALID_WIDGET_TYPES}. "
                    "To add charts, bar graphs, trend lines, tables, or metric KPI cards, "
                    "use widget_type='chart' with chart_config.chartType ('bar'|'line'|'counter'|'table'|'pie'|'combo'|...)."
                ),
            )

        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            pages = d.pages or []
            page = next((p for p in pages if p.get("id") == page_id), None)
            if page is None:
                avail_pages = [{"id": p.get("id"), "name": p.get("name")} for p in pages]
                return NovaToolResult(
                    ok=False,
                    error=f"ValidationError: Page '{page_id}' not found in dashboard. Available pages: {avail_pages}",
                )

            chart_config = None
            if widget_type == "chart":
                raw_cfg = arguments.get("chart_config")
                if not isinstance(raw_cfg, dict):
                    return NovaToolResult(
                        ok=False,
                        error="ValidationError: 'chart_config' object is required when widget_type='chart'. Must specify chartType and datasetId. Use describe_widget for examples.",
                    )
                chart_config = _normalize_chart_config(raw_cfg)
                chart_type = str(chart_config.get("chartType") or "").strip().lower()
                if not chart_type or chart_type not in VALID_CHART_TYPES:
                    return NovaToolResult(
                        ok=False,
                        error=f"ValidationError: Invalid or missing chartType in chart_config ('{chart_type}'). Must be one of: {VALID_CHART_TYPES}.",
                    )
                chart_config["chartType"] = chart_type

                dataset_id = chart_config.get("datasetId")
                if not dataset_id:
                    avail_ds = [{"id": ds.get("id"), "name": ds.get("name")} for ds in (d.datasets or [])]
                    return NovaToolResult(
                        ok=False,
                        error=f"ValidationError: 'datasetId' is required in chart_config. Available datasets on this dashboard: {avail_ds}.",
                    )

                valid_ds_ids = {ds.get("id") for ds in (d.datasets or [])}
                if dataset_id not in valid_ds_ids:
                    avail_ds = [{"id": ds.get("id"), "name": ds.get("name")} for ds in (d.datasets or [])]
                    return NovaToolResult(
                        ok=False,
                        error=f"ValidationError: datasetId '{dataset_id}' does not exist on this dashboard. Available datasets: {avail_ds}.",
                    )

            widget_id = str(uuid.uuid4())

            # Build grid item — auto-stack below existing widgets if no position given
            raw_grid = arguments.get("grid_item") or {}
            existing_widgets_on_page = [w for w in (d.widgets or []) if isinstance(w, dict) and w.get("pageId") == page_id]
            max_y = max(
                (
                    (w.get("gridItem") or {}).get("y", 0) + (w.get("gridItem") or {}).get("h", 4)
                    for w in existing_widgets_on_page
                ),
                default=0,
            )
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

            if chart_config is not None:
                new_widget["chartConfig"] = chart_config

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
            return NovaToolResult(
                ok=True,
                result={
                    "widgetId": widget_id,
                    "widgetType": widget_type,
                    "gridItem": grid_item,
                    "chartConfig": new_widget.get("chartConfig"),
                    "message": f"Widget '{widget_type}' (chartType: {chart_config.get('chartType') if chart_config else None}) added to page successfully.",
                },
            )
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
                merged_cfg = {**existing_cfg, **patch_cfg}
                if "datasetId" in merged_cfg:
                    valid_ds_ids = {ds.get("id") for ds in (d.datasets or [])}
                    if merged_cfg["datasetId"] not in valid_ds_ids:
                        avail_ds = [{"id": ds.get("id"), "name": ds.get("name")} for ds in (d.datasets or [])]
                        return NovaToolResult(
                            ok=False,
                            error=f"ValidationError: datasetId '{merged_cfg['datasetId']}' does not exist on dashboard. Available: {avail_ds}",
                        )
                if "chartType" in merged_cfg and merged_cfg["chartType"] not in VALID_CHART_TYPES:
                    return NovaToolResult(
                        ok=False,
                        error=f"ValidationError: Invalid chartType '{merged_cfg['chartType']}'. Must be one of: {VALID_CHART_TYPES}",
                    )
                target["chartConfig"] = merged_cfg
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
                wh = get_warehouse_by_id(system_db, warehouse_id)
                if not wh:
                    return NovaToolResult(ok=False, error=f"Warehouse '{warehouse_id}' not found")
                warehouse = wh
            else:
                warehouses = list_warehouses(system_db, workspace_id=workspace_id)
                running = [w for w in warehouses if getattr(w, "status", None) and str(w.status).lower() == "running"]
                if not running and warehouses:
                    running = warehouses
                if not running:
                    return NovaToolResult(ok=False, error="No active SQL warehouse found in workspace.")
                warehouse = running[0]

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
        workspace_id = _workspace_id_from_context(context)
        actor = context.get("user") or context.get("principal_id") or "agent"
        db = _get_account_db()
        try:
            d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if not d:
                return NovaToolResult(ok=False, error=f"Dashboard '{dashboard_id}' not found")

            d.is_draft = False
            d.published_at = datetime.now(timezone.utc)
            try:
                _register_in_catalog(db, workspace_id, d.id, d.name, actor)
            except Exception as catalog_exc:
                logger.warning("Failed to sync dashboard in catalog on publish: %s", catalog_exc)

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
    DescribeWidgetTool(),
    CreateDashboardTool(),
    UpdateDashboardTool(),
    AddDatasetTool(),
    UpdateDatasetTool(),
    AddWidgetTool(),
    UpdateWidgetTool(),
    RunQueryTool(),
    PublishDashboardTool(),
]

