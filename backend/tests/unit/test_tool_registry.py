"""Unit tests for the SOLID ToolRegistry implementation."""

from __future__ import annotations

import pytest
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.registry import ToolRegistry, tool_registry, TOOL_MAP, TOOL_REGISTRY


class DummyTestTool(BaseTool):
    key = "dummy_custom_tool"
    name = "Dummy Custom Tool"
    description = "A dummy tool for registry testing."
    input_schema = {
        "type": "object",
        "properties": {"param": {"type": "string"}},
        "required": ["param"],
    }

    def execute(self, args, agent, db):
        return ToolResult(ok=True, result={"param": args.get("param")})


def test_tool_registry_singleton_contains_core_tools():
    assert tool_registry.get("sql_query") is not None
    assert tool_registry.get("python_code") is not None
    assert tool_registry.get("asset_manager") is not None
    assert tool_registry.get("create_plan") is not None


def test_tool_registry_open_closed_registration():
    custom_registry = ToolRegistry()
    dummy = DummyTestTool()

    # Before registration
    assert custom_registry.get("dummy_custom_tool") is None

    # Register
    custom_registry.register(dummy)
    assert custom_registry.get("dummy_custom_tool") is dummy
    assert dummy in custom_registry.list_tools()

    # Definitions
    defs = custom_registry.get_definitions(["dummy_custom_tool"])
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "dummy_custom_tool"
    assert defs[0]["function"]["parameters"] == dummy.input_schema

    # Unregister
    custom_registry.unregister("dummy_custom_tool")
    assert custom_registry.get("dummy_custom_tool") is None


def test_backward_compatible_proxies():
    assert "sql_query" in TOOL_MAP
    assert TOOL_MAP.get("sql_query") is not None
    assert len(TOOL_REGISTRY) > 0
