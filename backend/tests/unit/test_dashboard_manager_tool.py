from types import SimpleNamespace
from unittest.mock import patch

from app.agents.services.agent.tools.platform.dashboards.dashboard_manager_tool import (
    DashboardManagerTool,
)
from app.nova.services.dashboard_tools import (
    CreateDashboardTool,
    _normalize_chart_config,
    _reconcile_widgets_with_pages,
)


def test_dashboard_manager_hides_context_from_agent_schema():
    assert "context" not in DashboardManagerTool.input_schema["properties"]
    assert DashboardManagerTool.input_schema["additionalProperties"] is False


def test_create_dashboard_requires_catalog_and_schema():
    required = CreateDashboardTool.input_schema["required"]

    assert "catalog_name" in required
    assert "schema_name" in required


def test_create_dashboard_rejects_missing_catalog_and_schema():
    result = CreateDashboardTool().execute(
        {"name": "Capacity"},
        {"workspace_id": "23b16411-6c9b-488e-b3b9-8dc9daa22d31"},
    )

    assert result.ok is False
    assert result.error == "catalog_name and schema_name are required to create a dashboard"


def test_page_replacement_moves_orphaned_widgets_to_first_page():
    pages = [{"id": "new-page", "name": "Single View", "layout": []}]
    widgets = [
        {
            "id": "widget-1",
            "pageId": "removed-page",
            "gridItem": {"i": "widget-1", "x": 0, "y": 0, "w": 4, "h": 2},
        }
    ]

    reconciled = _reconcile_widgets_with_pages(pages, widgets)

    assert reconciled[0]["pageId"] == "new-page"
    assert pages[0]["layout"] == [widgets[0]["gridItem"]]


def test_dashboard_manager_uses_backend_workspace_context():
    tool = DashboardManagerTool()
    agent = SimpleNamespace(
        workspace_id="23b16411-6c9b-488e-b3b9-8dc9daa22d31",
        created_by="owner@example.com",
    )
    args = {
        "operation": "create_dashboard",
        "payload": {"name": "Capacity"},
        "context": {"workspace_id": "current", "user": "untrusted"},
    }

    with patch(
        "app.agents.services.agent.tools.platform.dashboards.dashboard_manager_tool.execute_dashboard_manager_operation",
        return_value={"ok": True, "data": {}, "error": None},
    ) as execute_operation:
        result = tool.execute(args, agent, db=None)

    assert result.ok is True
    execute_operation.assert_called_once_with(
        operation="create_dashboard",
        payload={"name": "Capacity"},
        context={
            "workspace_id": "23b16411-6c9b-488e-b3b9-8dc9daa22d31",
            "user": "owner@example.com",
        },
    )


def test_dashboard_manager_passes_payload_warehouse_id_to_trusted_context():
    tool = DashboardManagerTool()
    agent = SimpleNamespace(workspace_id="workspace-id", created_by=None)
    payload = {"sql": "SELECT 1", "warehouse_id": "warehouse-id"}

    with patch(
        "app.agents.services.agent.tools.platform.dashboards.dashboard_manager_tool.execute_dashboard_manager_operation",
        return_value={"ok": True, "data": {}, "error": None},
    ) as execute_operation:
        tool.execute(
            {"operation": "run_query", "payload": payload},
            agent,
            db=None,
        )

    execute_operation.assert_called_once_with(
        operation="run_query",
        payload=payload,
        context={
            "workspace_id": "workspace-id",
            "user": "agent",
            "warehouse_id": "warehouse-id",
        },
    )


def test_chart_config_normalizes_title_row_background():
    normalized = _normalize_chart_config({
        "chart_type": "table",
        "dataset_id": "123",
        "title_row_bg": "#1e293b",
        "header_color": "#ffffff",
    })

    assert normalized["chartType"] == "table"
    assert normalized["datasetId"] == "123"
    assert normalized["titleRowBg"] == "#1e293b"
    assert normalized["titleRowColor"] == "#ffffff"
