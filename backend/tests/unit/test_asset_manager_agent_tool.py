from types import SimpleNamespace

from app.agents.services.agent.tools.platform.asset_manager.asset_manager_tool import AssetManagerTool
from app.agents.services.agent.tools.platform.asset_manager.operations import execute_asset_manager_operation
from app.agents.services.agent.tools.registry import get_tool_definitions


def test_asset_manager_tool_definition_registered():
    definitions = get_tool_definitions(["asset_manager"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "asset_manager"
    assert "create_asset" in function["parameters"]["properties"]["operation"]["enum"]


def test_unknown_operation_returns_tool_error():
    result = AssetManagerTool().execute(
        {"operation": "delete_asset", "payload": {}},
        agent=SimpleNamespace(created_by="tester"),
        db=SimpleNamespace(),
    )

    assert result.ok is False
    assert "Unsupported asset_manager operation" in result.error
    assert result.result["operation"] == "delete_asset"


def test_payload_must_be_object():
    result = AssetManagerTool().execute(
        {"operation": "list_asset_types", "payload": "bad"},
        agent=SimpleNamespace(created_by="tester"),
        db=SimpleNamespace(),
    )

    assert result.ok is False
    assert result.error == "payload must be an object"


def test_list_asset_types_dispatch_uses_asset_service(monkeypatch):
    captured = {}

    def fake_list_asset_types(db, industry_tag, category):
        captured["db"] = db
        captured["industry_tag"] = industry_tag
        captured["category"] = category
        return [
            SimpleNamespace(
                id=7,
                name="Pump",
                slug="pump",
                category="EQUIPMENT",
                description="Rotating equipment",
                industry_tags=["oil-gas"],
                icon=None,
                allowed_parents=[],
                allowed_children=[],
                is_root=False,
                is_leaf=True,
                schema_version=1,
            )
        ]

    monkeypatch.setattr(
        "app.asset_manager.services.list_asset_types",
        fake_list_asset_types,
    )

    db = SimpleNamespace()
    result = execute_asset_manager_operation(
        "list_asset_types",
        {"industry_tag": "oil-gas", "category": "EQUIPMENT"},
        db=db,
    )

    assert captured == {"db": db, "industry_tag": "oil-gas", "category": "EQUIPMENT"}
    assert result["ok"] is True
    assert result["operation"] == "list_asset_types"
    assert result["data"][0]["slug"] == "pump"


def test_search_asset_tags_dispatch(monkeypatch):
    captured = {}

    def fake_list_asset_tags(db, asset_id=None):
        captured["db"] = db
        captured["asset_id"] = asset_id
        return [
            SimpleNamespace(
                id=123,
                asset_id=456,
                asset_type_tag_id=None,
                tag_id="WTG01.ACTIVE_POWER",
                tag_name="Active Power Output",
                parameter="Power",
                unit="kW",
                source="PI",
                is_primary=True,
                created_at="2026-07-06T00:00:00",
                asset_type_tag=None,
            )
        ]

    monkeypatch.setattr(
        "app.asset_manager.services.list_asset_tags",
        fake_list_asset_tags,
    )

    db = SimpleNamespace()
    result = execute_asset_manager_operation(
        "search_asset_tags",
        {"asset_id": 456, "q": "active_power"},
        db=db,
    )

    assert captured == {"db": db, "asset_id": 456}
    assert result["ok"] is True
    assert result["operation"] == "search_asset_tags"
    assert result["data"][0]["tag_id"] == "WTG01.ACTIVE_POWER"


def test_search_asset_type_tags_dispatch(monkeypatch):
    captured = {}

    def fake_list_asset_type_tags(db, type_id):
        captured["db"] = db
        captured["type_id"] = type_id
        return [
            SimpleNamespace(
                id=11,
                asset_type_id=22,
                tag_key="active_power",
                name="Active Power",
                parameter="Power",
                unit="kW",
                description="Active power tag definition",
                is_required=True,
                created_at="2026-07-06T00:00:00",
                updated_at="2026-07-06T00:00:00",
            )
        ]

    monkeypatch.setattr(
        "app.asset_manager.services.list_asset_type_tags",
        fake_list_asset_type_tags,
    )

    db = SimpleNamespace()
    result = execute_asset_manager_operation(
        "search_asset_type_tags",
        {"type_id": 22, "q": "active_power"},
        db=db,
    )

    assert captured == {"db": db, "type_id": 22}
    assert result["ok"] is True
    assert result["operation"] == "search_asset_type_tags"
    assert result["data"][0]["tag_key"] == "active_power"
