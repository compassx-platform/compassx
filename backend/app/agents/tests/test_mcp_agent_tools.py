"""Test Agent MCP Server Attachment and Discovery."""

import pytest
from app.agents.schemas.agent_manifest import AgentManifest, BaseProfile
from app.agents.services.agent.tools.mcp_client_tool import ExternalMCPTool


def test_agent_manifest_mcp_servers():
    manifest = AgentManifest.default_for_profile(BaseProfile.REACTIVE_AGENT)
    assert manifest.mcp_servers == []

    manifest.mcp_servers = ["bluepine.static_data.postgres_mcp", "github_mcp"]
    dumped = manifest.model_dump()
    assert dumped["mcp_servers"] == ["bluepine.static_data.postgres_mcp", "github_mcp"]

    reloaded = AgentManifest.model_validate(dumped)
    assert reloaded.mcp_servers == ["bluepine.static_data.postgres_mcp", "github_mcp"]


def test_external_mcp_tool_definition():
    tool = ExternalMCPTool(
        server_id=1,
        server_name="postgres_mcp",
        tool_name="query",
        description="Execute read-only SQL queries on the database",
        input_schema={
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
    )

    openai_def = tool.to_openai_definition()
    assert openai_def["type"] == "function"
    assert openai_def["function"]["name"] == "query"
    assert openai_def["function"]["description"] == "Execute read-only SQL queries on the database"
    assert "sql" in openai_def["function"]["parameters"]["properties"]
