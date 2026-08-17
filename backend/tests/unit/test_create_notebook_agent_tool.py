from types import SimpleNamespace
import pytest
from app.agents.services.agent.tools.create_notebook_tool import CreateNotebookTool
from app.agents.services.agent.tools.registry import get_tool_definitions

def test_create_notebook_tool_definition_registered():
    definitions = get_tool_definitions(["create_notebook"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "create_notebook"
    assert "catalog_name" in function["parameters"]["properties"]
    assert "schema_name" in function["parameters"]["properties"]
    assert "notebook_name" in function["parameters"]["properties"]


def test_create_notebook_execution(monkeypatch):
    captured = {}

    async def fake_create_notebook(db, catalog_name, schema_name, body, user):
        captured["db"] = db
        captured["catalog_name"] = catalog_name
        captured["schema_name"] = schema_name
        captured["body"] = body
        captured["user"] = user
        return SimpleNamespace(
            id="nb-123",
            catalog_name=catalog_name,
            schema_name=schema_name,
            name=body.name,
            blob_path="nb-123.ipynb",
            storage_location="s3://bucket/nb-123.ipynb",
            owner="tester",
            comment=body.comment,
        )

    class FakeSession:
        def commit(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(
        "app.agents.services.agent.tools.create_notebook_tool.create_notebook",
        fake_create_notebook,
    )
    monkeypatch.setattr(
        "app.database.AccountSessionLocal",
        FakeSession,
    )

    db = FakeSession()
    agent = SimpleNamespace(created_by="tester@example.com")
    
    tool = CreateNotebookTool()
    result = tool.execute(
        {
            "catalog_name": "my_catalog",
            "schema_name": "my_schema",
            "notebook_name": "new_notebook",
            "comment": "My test notebook",
        },
        agent=agent,
        db=db,
    )

    assert result.ok is True
    assert result.result["name"] == "new_notebook"
    assert result.result["catalog_name"] == "my_catalog"
    assert result.result["schema_name"] == "my_schema"
    assert result.result["comment"] == "My test notebook"
    assert captured["catalog_name"] == "my_catalog"
    assert captured["schema_name"] == "my_schema"
    assert captured["body"].name == "new_notebook"
    assert captured["user"]["email"] == "tester@example.com"
