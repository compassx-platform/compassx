from types import SimpleNamespace
import pytest
from app.agents.services.agent.tools.catalog_editor_tool import CatalogEditorTool
from app.agents.services.agent.tools.registry import get_tool_definitions

def test_catalog_editor_tool_definition_registered():
    definitions = get_tool_definitions(["catalog_editor"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "catalog_editor"
    assert "operation" in function["parameters"]["properties"]
    assert "payload" in function["parameters"]["properties"]


def test_catalog_editor_execution_create_schema(monkeypatch):
    captured = {}

    def fake_create_schema(db, catalog_name, body, user):
        captured["catalog_name"] = catalog_name
        captured["body"] = body
        captured["user"] = user
        return SimpleNamespace(
            id="sch-123",
            catalog_id="cat-456",
            name=body.name,
            description=body.description,
            created_by=user["email"],
        )

    class FakeSession:
        def commit(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(
        "app.agents.services.agent.tools.catalog_editor_tool.create_schema",
        fake_create_schema,
    )
    monkeypatch.setattr(
        "app.database.AccountSessionLocal",
        FakeSession,
    )

    db = FakeSession()
    agent = SimpleNamespace(created_by="tester@example.com")
    
    tool = CatalogEditorTool()
    result = tool.execute(
        {
            "operation": "create_schema",
            "payload": {
                "catalog_name": "my_catalog",
                "schema_name": "new_schema",
                "description": "A new schema description",
            },
        },
        agent=agent,
        db=db,
    )

    assert result.ok is True
    assert result.result["operation"] == "create_schema"
    assert result.result["schema"]["name"] == "new_schema"
    assert result.result["schema"]["description"] == "A new schema description"
    assert captured["catalog_name"] == "my_catalog"
    assert captured["body"].name == "new_schema"
    assert captured["user"]["email"] == "tester@example.com"


def test_catalog_editor_execution_delete_schema(monkeypatch):
    captured = {}

    def fake_delete_schema(db, catalog_name, schema_name):
        captured["catalog_name"] = catalog_name
        captured["schema_name"] = schema_name

    class FakeSession:
        def close(self):
            pass

    monkeypatch.setattr(
        "app.agents.services.agent.tools.catalog_editor_tool.delete_schema",
        fake_delete_schema,
    )
    monkeypatch.setattr(
        "app.database.AccountSessionLocal",
        FakeSession,
    )

    db = FakeSession()
    agent = SimpleNamespace(created_by="tester@example.com")

    tool = CatalogEditorTool()
    result = tool.execute(
        {
            "operation": "delete_schema",
            "payload": {
                "catalog_name": "my_catalog",
                "schema_name": "old_schema",
            },
        },
        agent=agent,
        db=db,
    )

    assert result.ok is True
    assert result.result["operation"] == "delete_schema"
    assert result.result["status"] == "deleted"
    assert captured["catalog_name"] == "my_catalog"
    assert captured["schema_name"] == "old_schema"


def test_catalog_editor_execution_create_volume(monkeypatch):
    captured = {}

    async def fake_create_volume(db, catalog_name, schema_name, body, user):
        captured["catalog_name"] = catalog_name
        captured["schema_name"] = schema_name
        captured["body"] = body
        captured["user"] = user
        return SimpleNamespace(
            id="vol-789",
            schema_id="sch-123",
            name=body.name,
            description=body.description,
            storage_location="s3://bucket/volumes/vol-789",
            owner="tester",
            created_by=user["email"],
        )

    class FakeSession:
        def commit(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(
        "app.agents.services.agent.tools.catalog_editor_tool.create_volume",
        fake_create_volume,
    )
    monkeypatch.setattr(
        "app.database.AccountSessionLocal",
        FakeSession,
    )

    db = FakeSession()
    agent = SimpleNamespace(created_by="tester@example.com")

    tool = CatalogEditorTool()
    result = tool.execute(
        {
            "operation": "create_volume",
            "payload": {
                "catalog_name": "my_catalog",
                "schema_name": "my_schema",
                "volume_name": "new_volume",
                "description": "My first volume",
            },
        },
        agent=agent,
        db=db,
    )

    assert result.ok is True
    assert result.result["operation"] == "create_volume"
    assert result.result["volume"]["name"] == "new_volume"
    assert result.result["volume"]["description"] == "My first volume"
    assert captured["catalog_name"] == "my_catalog"
    assert captured["schema_name"] == "my_schema"
    assert captured["body"].name == "new_volume"
    assert captured["user"]["email"] == "tester@example.com"
