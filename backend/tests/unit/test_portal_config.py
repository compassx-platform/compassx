"""Portal layout actions keep their workspace rules after the split."""
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.catalog.models import CatalogWorkspaceBinding, UnifiedCatalogDashboard
from app.portal.application.update_portal_settings import update_portal_settings
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
from app.schemas.portal_config import PortalConfigUpdate, PortalItem, PortalSection, PortalSettingsUpdate


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
    return SimpleNamespace(workspace_id=workspace_id, require_workspace_admin=lambda action: None)


def _app(app_type="react", app_id="app_abc", workspace_id="ws_1", workspace_slug="plant"):
    return SimpleNamespace(
        id=app_id,
        name="Capacity",
        slug="capacity",
        description="overview",
        app_type=app_type,
        status="active",
        route="/capacity",
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
    )


def _dashboard(is_draft=False, dashboard_id="dash-1", name="Output"):
    return SimpleNamespace(
        id=dashboard_id,
        name=name,
        is_draft=is_draft,
        published_at=None,
    )


def _account_rows(dashboards, bindings=None, registrations=None):
    return {
        Dashboard: dashboards,
        CatalogWorkspaceBinding: bindings if bindings is not None else [
            SimpleNamespace(workspace_id="ws_1", catalog_id="cat_1"),
        ],
        UnifiedCatalogDashboard: registrations if registrations is not None else [
            SimpleNamespace(dashboard_id="dash-1", schema=SimpleNamespace(catalog_id="cat_1")),
        ],
    }


def test_router_keeps_the_three_portal_paths():
    paths = sorted((route.path, tuple(sorted(route.methods))) for route in router.routes)
    assert paths == [
        ("/api/v1/portal/available-items", ("GET",)),
        ("/api/v1/portal/config", ("GET",)),
        ("/api/v1/portal/config", ("PUT",)),
        ("/api/v1/portal/settings", ("PATCH",)),
    ]


def test_missing_layout_bootstraps_apps_and_every_dashboard():
    sdb = _Session({PortalConfig: None, App: [_app("streamlit"), _app(app_id="app_other", workspace_id="ws_9")]})
    adb = _Session(_account_rows([
        _dashboard(is_draft=True),
        _dashboard(dashboard_id="dash-other", name="Elsewhere"),
    ], registrations=[
        SimpleNamespace(dashboard_id="dash-1", schema=SimpleNamespace(catalog_id="cat_1")),
        SimpleNamespace(dashboard_id="dash-other", schema=SimpleNamespace(catalog_id="cat_9")),
    ]))

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
    assert [item.target_id for item in result.sections[0].items] == ["app_abc"]
    assert result.sections[1].title == "Dashboards"
    assert result.sections[1].items[0].status == "draft"
    assert result.sections[1].items[0].target_id == "dash-1"
    assert [item.target_id for item in result.sections[1].items] == ["dash-1"]
    assert sdb.added[0].created_by_user_id is None
    assert sdb.committed == 1


def test_bootstrap_failure_is_logged_and_still_returned(caplog):
    sdb = _Session({PortalConfig: None, App: []})
    adb = _Session(_account_rows([], bindings=[], registrations=[]))

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
    sdb = _Session({App: [_app("fastline"), _app(app_id="app_other", workspace_id="ws_9")]})
    adb = _Session(_account_rows([
        _dashboard(),
        _dashboard(dashboard_id="dash-other", name="Elsewhere"),
    ], registrations=[
        SimpleNamespace(dashboard_id="dash-1", schema=SimpleNamespace(catalog_id="cat_1")),
        SimpleNamespace(dashboard_id="dash-other", schema=SimpleNamespace(catalog_id="cat_9")),
    ]))

    result = get_available_items(
        request=None,
        workspace_id=None,
        workspace_slug="plant",
        sdb=sdb,
        adb=adb,
        guard=_guard(),
    )

    assert [item.id for item in result.apps] == ["app_abc"]
    assert result.apps[0].app_type == "fastline"
    assert result.apps[0].route == "/capacity"
    assert [item.id for item in result.dashboards] == ["dash-1"]
    assert result.dashboards[0].description is None
    assert result.dashboards[0].is_draft is False


def test_unknown_app_type_uses_code2_icon():
    sdb = _Session({PortalConfig: None, App: [_app("fastline", workspace_id="ws_9")]})
    adb = _Session(_account_rows([], bindings=[], registrations=[]))

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


def test_saved_layout_hides_items_from_other_workspaces():
    existing = PortalConfig(
        id="portal_cfg_existing",
        workspace_id="ws_1",
        workspace_slug="plant",
        sections=[{
            "id": "sec_mixed",
            "title": "Mixed",
            "items": [
                {"id": "item_app_app_abc", "type": "app", "target_id": "app_abc", "title": "Capacity", "is_visible": True, "order": 0},
                {"id": "item_app_app_other", "type": "app", "target_id": "app_other", "title": "Other", "is_visible": True, "order": 1},
                {"id": "item_dash_dash-1", "type": "dashboard", "target_id": "dash-1", "title": "Output", "is_visible": True, "order": 2},
                {"id": "item_dash_dash-other", "type": "dashboard", "target_id": "dash-other", "title": "Elsewhere", "is_visible": True, "order": 3},
                {"id": "item_ext_1", "type": "external_link", "target_id": "ext_1", "title": "Docs", "is_visible": True, "order": 4, "url": "https://example.com"},
            ],
        }],
    )
    existing.created_at = datetime.now(timezone.utc)
    sdb = _Session({
        PortalConfig: existing,
        App: [_app(), _app(app_id="app_other", workspace_id="ws_9")],
    })
    adb = _Session(_account_rows(
        [_dashboard(), _dashboard(dashboard_id="dash-other", name="Elsewhere")],
        registrations=[
            SimpleNamespace(dashboard_id="dash-1", schema=SimpleNamespace(catalog_id="cat_1")),
            SimpleNamespace(dashboard_id="dash-other", schema=SimpleNamespace(catalog_id="cat_9")),
        ],
    ))

    result = get_portal_config(
        request=None,
        workspace_id=None,
        workspace_slug="plant",
        sdb=sdb,
        adb=adb,
        guard=_guard(),
    )

    assert [item.target_id for item in result.sections[0].items] == ["app_abc", "dash-1", "ext_1"]


def test_logo_save_keeps_the_sidebar_and_rejects_other_files():
    existing = PortalConfig(
        id="portal_cfg_existing",
        workspace_id="ws_1",
        workspace_slug="plant",
        sections=[{"id": "sec_apps", "title": "Applications", "items": []}],
        settings={},
    )
    sdb = _Session({PortalConfig: existing})

    saved = update_portal_settings(
        body=PortalSettingsUpdate(logo="data:image/png;base64,aaaa"),
        request=None,
        workspace_id="ws_1",
        workspace_slug="plant",
        sdb=sdb,
        guard=_guard(),
        adb=None,
    )

    assert saved.logo == "data:image/png;base64,aaaa"
    assert existing.sections[0]["id"] == "sec_apps"
    assert sdb.committed == 1

    try:
        update_portal_settings(
            body=PortalSettingsUpdate(logo="data:text/html,hi"),
            request=None,
            workspace_id="ws_1",
            workspace_slug="plant",
            sdb=sdb,
            guard=_guard(),
            adb=None,
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("a non-image logo was accepted")
