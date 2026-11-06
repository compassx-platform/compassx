"""Portal layout actions keep their workspace rules after the split."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.app import App
from app.models.dashboard import Dashboard
from app.models.portal_config import PortalConfig
from app.routes.portal_routes import (
    _bootstrap_default_config,
    get_available_items,
    get_portal_config,
    router,
    update_portal_config,
)
from app.schemas.portal_config import PortalConfigUpdate, PortalItem, PortalSection


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        value = self.value() if callable(self.value) else self.value
        return value

    def all(self):
        value = self.value() if callable(self.value) else self.value
        return list(value or [])


class _Session:
    def __init__(self, handlers):
        self.handlers = handlers
        self.added = []
        self.committed = 0
        self.refreshed = []

    def query(self, model):
        return _Query(self.handlers[model])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = obj.created_at
        self.refreshed.append(obj)

    def rollback(self):
        self.rolled_back = True


def _guard(workspace_id="ws_1"):
    return SimpleNamespace(workspace_id=workspace_id)


def _app(app_type="react"):
    return SimpleNamespace(
        id="app_abc",
        name="Capacity",
        slug="capacity",
        description="overview",
        app_type=app_type,
        status="active",
        route="/capacity",
        workspace_id="ws_1",
        workspace_slug="plant",
    )


def _dashboard(is_draft=False):
    return SimpleNamespace(
        id="dash-1",
        name="Output",
        is_draft=is_draft,
        published_at=None,
    )


def test_router_keeps_the_three_portal_paths():
    paths = sorted((route.path, tuple(sorted(route.methods))) for route in router.routes)
    assert paths == [
        ("/api/v1/portal/available-items", ("GET",)),
        ("/api/v1/portal/config", ("GET",)),
        ("/api/v1/portal/config", ("PUT",)),
    ]


def test_missing_layout_bootstraps_apps_and_every_dashboard():
    sdb = _Session({PortalConfig: None, App: [_app("streamlit")]})
    adb = _Session({Dashboard: [_dashboard(is_draft=True)]})

    result = get_portal_config(
        request=None,
        workspace_id=None,
        workspace_slug="plant",
        sdb=sdb,
        adb=adb,
        guard=_guard(),
    )

    assert result.workspace_id == "ws_1"
    assert result.id.startswith("portal_cfg_")
    assert result.sections[0].title == "Applications"
    assert result.sections[0].items[0].icon == "Sparkles"
    assert result.sections[0].items[0].id == "item_app_app_abc"
    assert result.sections[1].title == "Dashboards"
    assert result.sections[1].items[0].status == "draft"
    assert result.sections[1].items[0].target_id == "dash-1"
    assert sdb.added[0].created_by_user_id is None
    assert sdb.committed == 1


def test_bootstrap_failure_is_logged_and_still_returned(caplog):
    sdb = _Session({PortalConfig: None, App: []})
    adb = _Session({Dashboard: []})

    def boom():
        raise RuntimeError("disk full")

    sdb.commit = boom

    with caplog.at_level("WARNING", logger="app.routes.portal_routes"):
        result = _bootstrap_default_config("ws_1", "plant", sdb, adb, user_id="ignored")

    assert result.sections[0]["id"] == "sec_applications"
    assert result.sections[0]["items"] == []
    assert sdb.rolled_back is True
    assert "Could not persist auto-bootstrapped portal config: disk full" in caplog.text


def test_save_updates_the_existing_row_and_marks_sections():
    existing = PortalConfig(
        id="portal_cfg_existing",
        workspace_id="ws_1",
        workspace_slug="old",
        sections=[],
    )
    existing.created_at = datetime.now(timezone.utc)
    sdb = _Session({PortalConfig: existing})
    body = PortalConfigUpdate(
        sections=[
            PortalSection(
                id="sec_operations",
                title="Operations",
                items=[
                    PortalItem(
                        id="item_ext_1",
                        type="external_link",
                        target_id="ext_1",
                        title="Documentation Hub",
                        icon="Globe",
                        url="https://example.com",
                    )
                ],
            )
        ]
    )

    result = update_portal_config(
        body=body,
        request=None,
        workspace_id="ws_1",
        workspace_slug="plant",
        sdb=sdb,
        guard=_guard(),
    )

    assert result.sections[0].title == "Operations"
    assert existing.workspace_slug == "plant"
    assert existing.updated_at is not None
    assert sdb.committed == 1


def test_available_items_keep_dashboard_description_empty():
    sdb = _Session({App: [_app("fastline")]})
    adb = _Session({Dashboard: [_dashboard()]})

    result = get_available_items(
        request=None,
        workspace_id=None,
        workspace_slug="plant",
        sdb=sdb,
        adb=adb,
        guard=_guard(None),
    )

    assert result.apps[0].app_type == "fastline"
    assert result.apps[0].route == "/capacity"
    assert result.dashboards[0].description is None
    assert result.dashboards[0].is_draft is False


def test_unknown_app_type_uses_code2_icon():
    sdb = _Session({PortalConfig: None, App: [_app("fastline")]})
    adb = _Session({Dashboard: []})

    result = get_portal_config(
        request=None,
        workspace_id="ws_9",
        workspace_slug=None,
        sdb=sdb,
        adb=adb,
        guard=_guard("other"),
    )

    assert result.workspace_id == "ws_9"
    assert result.sections[0].items[0].icon == "Code2"
