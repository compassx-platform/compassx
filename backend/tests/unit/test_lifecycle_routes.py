"""Unit tests for lifecycle and auto-shutdown REST API endpoints."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.app import App
from app.models.dev_workspace import DevWorkspace
from app.models.compute_resources import ComputeResource
from app.routes.lifecycle_routes import (
    get_app_lifecycle,
    update_app_lifecycle,
    touch_app_activity_endpoint,
    get_compute_lifecycle,
    update_compute_lifecycle,
    touch_compute_activity_endpoint,
    AppLifecycleUpdateRequest,
    DevSandboxLifecycleConfig,
    AppRuntimeLifecycleConfig,
    ComputeLifecycleUpdateRequest,
    ActivityTouchRequest,
)


def _guard(workspace_id="ws-123"):
    guard = MagicMock()
    guard.workspace_id = workspace_id
    guard.principal = SimpleNamespace(id="user-123", email="user@test.com")
    return guard


def test_get_app_lifecycle():
    """Test retrieving app lifecycle configuration."""
    app = App(
        id="app-1",
        name="Dashboard App",
        slug="dashboard-app",
        workspace_id="ws-123",
        status="active",
        config={
            "dev_sandbox": {
                "auto_suspend_enabled": True,
                "idle_timeout_minutes": 45,
            },
            "app_runtime": {
                "auto_suspend_enabled": False,
                "idle_timeout_minutes": 120,
            },
        },
    )
    ws = DevWorkspace(
        id="ws-1",
        app_id="app-1",
        name="ws-main",
        folder_path="app-1/ws-main",
        status="active",
        last_active_at=datetime.now(timezone.utc),
    )

    mock_db = MagicMock()
    mock_db.query().filter().first.side_effect = [app]
    mock_db.query().filter().order_by().first.return_value = ws

    resp = get_app_lifecycle("app-1", db=mock_db, guard=_guard("ws-123"))

    assert resp["app_id"] == "app-1"
    assert resp["dev_sandbox"]["auto_suspend_enabled"] is True
    assert resp["dev_sandbox"]["idle_timeout_minutes"] == 45
    assert resp["app_runtime"]["auto_suspend_enabled"] is False
    assert resp["app_runtime"]["idle_timeout_minutes"] == 120


def test_update_app_lifecycle():
    """Test updating dev_sandbox and app_runtime lifecycle configuration."""
    app = App(
        id="app-2",
        name="FastAPI App",
        slug="fastapi-app",
        workspace_id="ws-123",
        status="active",
        config={},
    )
    ws = DevWorkspace(
        id="ws-2",
        app_id="app-2",
        name="ws-dev",
        folder_path="app-2/ws-dev",
        status="active",
        last_active_at=datetime.now(timezone.utc),
    )

    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = app
    mock_db.query().filter().order_by().first.return_value = ws

    update_body = AppLifecycleUpdateRequest(
        dev_sandbox=DevSandboxLifecycleConfig(
            auto_suspend_enabled=True,
            idle_timeout_minutes=30,
            auto_reap_enabled=True,
            stale_reap_days=14,
        ),
        app_runtime=AppRuntimeLifecycleConfig(
            auto_suspend_enabled=True,
            idle_timeout_minutes=60,
        ),
    )

    resp = update_app_lifecycle("app-2", body=update_body, db=mock_db, guard=_guard("ws-123"))

    assert app.config["dev_sandbox"]["auto_suspend_enabled"] is True
    assert app.config["dev_sandbox"]["idle_timeout_minutes"] == 30
    assert app.config["app_runtime"]["auto_suspend_enabled"] is True
    assert app.config["app_runtime"]["idle_timeout_minutes"] == 60


def test_touch_app_activity_endpoint():
    """Test explicit activity touch on an app."""
    app = App(
        id="app-3",
        name="React App",
        slug="react-app",
        workspace_id="ws-123",
        status="active",
        config={},
    )
    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = app

    with patch("app.routes.lifecycle_routes.unified_reaper_service.touch_app_activity") as mock_touch_app, \
         patch("app.routes.lifecycle_routes.unified_reaper_service.touch_dev_sandbox_activity") as mock_touch_dev:

        resp = touch_app_activity_endpoint(
            "app-3",
            body=ActivityTouchRequest(target="all"),
            db=mock_db,
            guard=_guard("ws-123"),
        )

        assert resp["status"] == "touched"
        mock_touch_app.assert_called_once_with("app-3")
        mock_touch_dev.assert_called_once_with("app-3")


def test_get_and_update_compute_lifecycle():
    """Test retrieving and updating compute resource lifecycle settings."""
    res = ComputeResource(
        id="comp-1",
        name="Ray Cluster",
        runtime="ray",
        profile="cloud-s",
        user_id="user-1",
        workspace_id="ws-123",
        desired_status="running",
        extra_env=json.dumps({"auto_suspend_enabled": True, "idle_timeout_minutes": 60}),
    )

    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = res

    # 1. Get
    get_resp = get_compute_lifecycle("comp-1", db=mock_db, guard=_guard("ws-123"))
    assert get_resp["resource_id"] == "comp-1"
    assert get_resp["auto_suspend_enabled"] is True
    assert get_resp["idle_timeout_minutes"] == 60

    # 2. Update
    upd_body = ComputeLifecycleUpdateRequest(
        auto_suspend_enabled=False,
        idle_timeout_minutes=120,
    )
    upd_resp = update_compute_lifecycle("comp-1", body=upd_body, db=mock_db, guard=_guard("ws-123"))
    assert upd_resp["auto_suspend_enabled"] is False
    assert upd_resp["idle_timeout_minutes"] == 120
