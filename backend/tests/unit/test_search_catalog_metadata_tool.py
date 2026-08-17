from types import SimpleNamespace
import pytest
from app.agents.services.agent.tools.search_catalog_metadata_tool import SearchCatalogMetadataTool
from app.agents.services.agent.tools.registry import get_tool_definitions

def test_search_catalog_metadata_tool_definition_registered():
    definitions = get_tool_definitions(["search_catalog_metadata"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "search_catalog_metadata"
    assert "query" in function["parameters"]["properties"]
    assert "object_type" in function["parameters"]["properties"]


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, limit_val):
        self.data = self.data[:limit_val]
        return self

    def join(self, *args, **kwargs):
        return self

    def all(self):
        return self.data


def test_search_catalog_metadata_execution(monkeypatch):
    fake_catalogs = [
        SimpleNamespace(
            name="test_catalog",
            description="A nice test catalog",
            catalog_type="postgres",
            database_name="test_db",
            created_by="system",
            created_at=None,
        )
    ]
    fake_schemas = [
        SimpleNamespace(
            name="test_schema",
            catalog=SimpleNamespace(name="test_catalog"),
            description="A test schema",
            created_by="system",
            created_at=None,
        )
    ]

    class FakeSession:
        def query(self, model):
            if model.__name__ == "UnifiedCatalog":
                return FakeQuery(fake_catalogs)
            elif model.__name__ == "UnifiedCatalogSchema":
                return FakeQuery(fake_schemas)
            return FakeQuery([])

        def close(self):
            pass

    monkeypatch.setattr(
        "app.database.AccountSessionLocal",
        FakeSession,
    )

    db = FakeSession()
    agent = SimpleNamespace(created_by="tester@example.com")
    
    tool = SearchCatalogMetadataTool()
    result = tool.execute(
        {
            "query": "test",
            "object_type": "all",
            "limit": 5,
        },
        agent=agent,
        db=db,
    )

    assert result.ok is True
    assert result.result["count"] == 2
    assert result.result["results"][0]["name"] == "test_catalog"
    assert result.result["results"][0]["object_type"] == "catalog"
    assert result.result["results"][1]["name"] == "test_schema"
    assert result.result["results"][1]["object_type"] == "schema"
