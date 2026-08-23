import pytest
import uuid
from unittest.mock import MagicMock, patch

from app.nova.services.dashboard_tools import (
    DescribeWidgetTool,
    AddWidgetTool,
    UpdateWidgetTool,
    UpdateDashboardTool,
    VALID_CHART_TYPES,
    VALID_WIDGET_TYPES,
)


def test_describe_widget_tool_list_all():
    tool = DescribeWidgetTool()
    res = tool.execute({}, {})
    assert res.ok is True
    assert "supportedChartTypes" in res.result
    assert "counter" in res.result["supportedChartTypes"]
    assert "bar" in res.result["supportedChartTypes"]
    assert "combo" in res.result["supportedChartTypes"]
    assert "waterfall" in res.result["supportedChartTypes"]


def test_describe_widget_tool_specific_chart():
    tool = DescribeWidgetTool()
    res = tool.execute({"chart_type": "combo"}, {})
    assert res.ok is True
    assert res.result["chartType"] == "combo"
    assert "y2Fields" in str(res.result["requiredFields"]) or "y2Fields" in str(res.result.get("example"))
    assert "example" in res.result


def test_add_widget_invalid_widget_type():
    tool = AddWidgetTool()
    # Passing "card" as widget_type should be rejected
    res = tool.execute({
        "dashboard_id": str(uuid.uuid4()),
        "page_id": str(uuid.uuid4()),
        "widget_type": "card",
    }, {})
    assert res.ok is False
    assert "ValidationError: Invalid widget_type 'card'" in res.error


def test_add_widget_missing_chart_config(db_session=None):
    mock_dashboard = MagicMock()
    mock_dashboard.id = str(uuid.uuid4())
    page_id = str(uuid.uuid4())
    mock_dashboard.pages = [{"id": page_id, "name": "Page 1", "layout": []}]
    mock_dashboard.datasets = []
    mock_dashboard.widgets = []

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_dashboard

    tool = AddWidgetTool()
    with patch("app.nova.services.dashboard_tools._get_account_db", return_value=mock_db):
        res = tool.execute({
            "dashboard_id": mock_dashboard.id,
            "page_id": page_id,
            "widget_type": "chart",
            # missing chart_config
        }, {})
        assert res.ok is False
        assert "ValidationError: 'chart_config' object is required" in res.error


def test_add_widget_invalid_chart_type():
    mock_dashboard = MagicMock()
    mock_dashboard.id = str(uuid.uuid4())
    page_id = str(uuid.uuid4())
    mock_dashboard.pages = [{"id": page_id, "name": "Page 1", "layout": []}]
    mock_dashboard.datasets = [{"id": "ds-1", "name": "test_ds"}]
    mock_dashboard.widgets = []

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_dashboard

    tool = AddWidgetTool()
    with patch("app.nova.services.dashboard_tools._get_account_db", return_value=mock_db):
        res = tool.execute({
            "dashboard_id": mock_dashboard.id,
            "page_id": page_id,
            "widget_type": "chart",
            "chart_config": {
                "chartType": "unsupported_magic_chart",
                "datasetId": "ds-1",
            },
        }, {})
        assert res.ok is False
        assert "ValidationError: Invalid or missing chartType" in res.error


def test_add_widget_missing_or_invalid_dataset_id():
    mock_dashboard = MagicMock()
    mock_dashboard.id = str(uuid.uuid4())
    page_id = str(uuid.uuid4())
    mock_dashboard.pages = [{"id": page_id, "name": "Page 1", "layout": []}]
    mock_dashboard.datasets = [{"id": "ds-valid-1", "name": "real_ds"}]
    mock_dashboard.widgets = []

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_dashboard

    tool = AddWidgetTool()
    with patch("app.nova.services.dashboard_tools._get_account_db", return_value=mock_db):
        # 1. Missing datasetId
        res1 = tool.execute({
            "dashboard_id": mock_dashboard.id,
            "page_id": page_id,
            "widget_type": "chart",
            "chart_config": {
                "chartType": "bar",
            },
        }, {})
        assert res1.ok is False
        assert "ValidationError: 'datasetId' is required" in res1.error

        # 2. Non-existent datasetId
        res2 = tool.execute({
            "dashboard_id": mock_dashboard.id,
            "page_id": page_id,
            "widget_type": "chart",
            "chart_config": {
                "chartType": "bar",
                "datasetId": "nonexistent-ds-uuid",
            },
        }, {})
        assert res2.ok is False
        assert "ValidationError: datasetId 'nonexistent-ds-uuid' does not exist" in res2.error


def test_add_widget_success():
    mock_dashboard = MagicMock()
    mock_dashboard.id = str(uuid.uuid4())
    page_id = str(uuid.uuid4())
    mock_dashboard.pages = [{"id": page_id, "name": "Page 1", "layout": []}]
    mock_dashboard.datasets = [{"id": "ds-123", "name": "site_capacity"}]
    mock_dashboard.widgets = []

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_dashboard

    tool = AddWidgetTool()
    with patch("app.nova.services.dashboard_tools._get_account_db", return_value=mock_db):
        res = tool.execute({
            "dashboard_id": mock_dashboard.id,
            "page_id": page_id,
            "widget_type": "chart",
            "title": "Capacity by Site",
            "chart_config": {
                "chartType": "bar",
                "datasetId": "ds-123",
                "xField": "site",
                "yFields": ["ac_mw"],
            },
            "grid_item": {"x": 0, "y": 0, "w": 6, "h": 6},
        }, {})
        assert res.ok is True
        assert res.result["widgetType"] == "chart"
        assert res.result["chartConfig"]["chartType"] == "bar"
        assert res.result["chartConfig"]["datasetId"] == "ds-123"
        assert len(mock_dashboard.widgets) == 1


def test_update_dashboard_pages():
    mock_dashboard = MagicMock()
    mock_dashboard.id = str(uuid.uuid4())
    mock_dashboard.name = "My Dashboard"
    mock_dashboard.is_draft = True
    mock_dashboard.pages = []
    mock_dashboard.settings = {}

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_dashboard

    tool = UpdateDashboardTool()
    with patch("app.nova.services.dashboard_tools._get_account_db", return_value=mock_db):
        res = tool.execute({
            "dashboard_id": mock_dashboard.id,
            "pages": ["Overview", "Generation", "Outages", "Cleaning"],
        }, {})
        assert res.ok is True
        assert len(mock_dashboard.pages) == 4
        assert mock_dashboard.pages[0]["name"] == "Overview"
        assert mock_dashboard.pages[3]["name"] == "Cleaning"
