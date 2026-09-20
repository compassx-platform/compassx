"""Unit tests for UnifiedReaperService (automated idle shutdown across dev sandboxes, apps, and compute runtimes)."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.sandbox_reaper_service import (
    SandboxReaperService,
    DEFAULT_DEV_IDLE_SUSPEND_SECONDS,
    DEFAULT_APP_IDLE_SUSPEND_SECONDS,
    DEFAULT_COMPUTE_IDLE_SUSPEND_SECONDS,
)


def _make_app(app_id="app-1", name="Test App", status="active", config=None):
    return SimpleNamespace(
        id=app_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        workspace_id="ws-123",
        status=status,
        config=config or {},
        created_at=datetime.now(timezone.utc) - timedelta(hours=5),
        updated_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )


def _make_dev_workspace(ws_id="ws-1", app_id="app-1", status="active", last_active_at=None):
    return SimpleNamespace(
        id=ws_id,
        app_id=app_id,
        name="workspace-1",
        folder_path=f"app-1/workspace-1",
        status=status,
        last_active_at=last_active_at or (datetime.now(timezone.utc) - timedelta(hours=3)),
    )


def _make_compute_resource(resource_id="comp-1", desired_status="running", extra_env=None):
    return SimpleNamespace(
        id=resource_id,
        name="Spark Cluster",
        runtime="spark",
        profile="cloud-s",
        user_id="user-1",
        workspace_id="ws-123",
        desired_status=desired_status,
        created_at=datetime.now(timezone.utc) - timedelta(hours=4),
        extra_env=extra_env or json.dumps({"auto_suspend_enabled": True, "idle_timeout_minutes": 60}),
    )


class MockDbSession:
    def __init__(self, data=None):
        self.data = data or {}
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def query(self, model):
        model_name = getattr(model, "__name__", str(model))
        items = self.data.get(model_name, [])

        class QueryMock:
            def __init__(self, items):
                self._items = list(items)

            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def first(self):
                return self._items[0] if self._items else None

            def all(self):
                return self._items

        return QueryMock(items)

    def commit(self):
        self.committed = True


def test_dev_sandbox_idle_sweep_suspends_when_inactive():
    """Dev sandboxes inactive beyond threshold should be suspended by reaper."""
    reaper = SandboxReaperService(idle_timeout_seconds=3600)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=7200)

    app = _make_app(app_id="app-dev-1", config={"dev_sandbox": {"auto_suspend_enabled": True, "idle_timeout_minutes": 60}})
    ws = _make_dev_workspace(ws_id="ws-1", app_id="app-dev-1", status="active", last_active_at=old_time)

    mock_db = MockDbSession({"DevWorkspace": [ws], "App": [app]})

    with patch("app.database.SystemSessionLocal", return_value=mock_db), \
         patch("app.services.drivers.factory.driver_factory.get_dev_driver") as mock_dev_driver, \
         patch("app.services.omnigent_dev_service.omnigent_dev_service.check_app_has_active_work", return_value=False), \
         patch("app.services.omnigent_dev_service.omnigent_dev_service.suspend_dev_session") as mock_suspend:

        mock_dev_driver.return_value.get_dev_status.return_value = {"status": "active", "phase": "Running"}

        reaper._sync_sweep_idle_workspaces()
        mock_suspend.assert_called_once_with(app)


def test_dev_sandbox_idle_sweep_skips_when_disabled():
    """Dev sandboxes with auto_suspend_enabled=False should NOT be suspended."""
    reaper = SandboxReaperService(idle_timeout_seconds=3600)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=7200)

    app = _make_app(app_id="app-dev-2", config={"dev_sandbox": {"auto_suspend_enabled": False}})
    ws = _make_dev_workspace(ws_id="ws-2", app_id="app-dev-2", status="active", last_active_at=old_time)

    mock_db = MockDbSession({"DevWorkspace": [ws], "App": [app]})

    with patch("app.database.SystemSessionLocal", return_value=mock_db), \
         patch("app.services.omnigent_dev_service.omnigent_dev_service.suspend_dev_session") as mock_suspend:

        reaper._sync_sweep_idle_workspaces()
        mock_suspend.assert_not_called()


def test_deployed_app_idle_sweep_suspends_when_enabled():
    """Deployed apps with auto_suspend_enabled=True and no traffic should be stopped."""
    reaper = SandboxReaperService(idle_timeout_seconds=3600)
    old_accessed = (datetime.now(timezone.utc) - timedelta(minutes=150)).isoformat()

    app = _make_app(
        app_id="app-prod-1",
        status="active",
        config={
            "app_runtime": {
                "auto_suspend_enabled": True,
                "idle_timeout_minutes": 120,
                "last_accessed_at": old_accessed,
            }
        },
    )

    mock_db = MockDbSession({"App": [app]})

    with patch("app.database.SystemSessionLocal", return_value=mock_db), \
         patch("app.services.app_runner.app_runner_service.get_runtime_status", return_value={"status": "active"}), \
         patch("app.services.app_runner.app_runner_service.stop_app") as mock_stop_app:

        reaper._sync_sweep_idle_apps()
        mock_stop_app.assert_called_once_with(app)
        assert app.status == "stopped"


def test_deployed_app_idle_sweep_skips_by_default():
    """Deployed apps without explicit auto_suspend_enabled=True should NOT be stopped (default 24/7)."""
    reaper = SandboxReaperService(idle_timeout_seconds=3600)

    app = _make_app(
        app_id="app-prod-2",
        status="active",
        config={},  # default: auto_suspend_enabled is False
    )

    mock_db = MockDbSession({"App": [app]})

    with patch("app.database.SystemSessionLocal", return_value=mock_db), \
         patch("app.services.app_runner.app_runner_service.stop_app") as mock_stop_app:

        reaper._sync_sweep_idle_apps()
        mock_stop_app.assert_not_called()


def test_compute_runtime_idle_sweep_suspends_when_inactive():
    """Compute runtimes inactive beyond idle threshold should be stopped."""
    reaper = SandboxReaperService(idle_timeout_seconds=3600)
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()

    extra_env = json.dumps({
        "auto_suspend_enabled": True,
        "idle_timeout_minutes": 60,
        "last_active_at": old_time,
    })
    comp = _make_compute_resource(resource_id="comp-1", desired_status="running", extra_env=extra_env)

    mock_db = MockDbSession({"ComputeResource": [comp], "PlatformRuntime": []})

    with patch("app.database.SystemSessionLocal", return_value=mock_db), \
         patch("app.compute.services.resource_service.ComputeResourceService.stop_resource") as mock_stop_resource:

        reaper._sync_sweep_idle_compute_resources()
        mock_stop_resource.assert_called_once_with("comp-1", user_id="user-1", workspace_id="ws-123")


def test_touch_activity_helpers():
    """Calling touch helpers should update the appropriate last_accessed_at and last_active_at timestamps."""
    reaper = SandboxReaperService()
    app = _make_app(app_id="app-touch-1", config={})
    comp = _make_compute_resource(resource_id="comp-touch-1", extra_env="{}")

    mock_db = MockDbSession({"App": [app], "ComputeResource": [comp], "PlatformRuntime": []})

    with patch("app.database.SystemSessionLocal", return_value=mock_db):
        reaper.touch_app_activity("app-touch-1")
        assert "last_accessed_at" in app.config
        assert "lifecycle" in app.config

        reaper.touch_compute_activity("comp-touch-1")
        env_dict = json.loads(comp.extra_env)
        assert "last_active_at" in env_dict
        assert "lifecycle" in env_dict
