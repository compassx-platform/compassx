"""Unit tests for AI Gateway MCP (Model Context Protocol) Module."""

import pytest
from unittest.mock import MagicMock

from app.ai_gateway.mcp.builtins.sql_warehouse_mcp import SQLWarehouseMCPServer
from app.ai_gateway.mcp.builtins.catalog_search_mcp import CatalogSearchMCPServer
from app.ai_gateway.mcp.manager import MCPManager
from app.ai_gateway.mcp.proxy import MCPExecutionProxy, _truncate_output


@pytest.mark.asyncio
async def test_sql_warehouse_mcp_list_tools():
    server = SQLWarehouseMCPServer()
    tools = server.list_tools()
    tool_names = [t.name for t in tools]
    assert "execute_sql" in tool_names
    assert "list_tables" in tool_names
    assert "describe_table" in tool_names


@pytest.mark.asyncio
async def test_catalog_search_mcp_list_tools():
    server = CatalogSearchMCPServer()
    tools = server.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "search_catalog"


@pytest.mark.asyncio
async def test_sql_warehouse_mcp_execute_safety():
    server = SQLWarehouseMCPServer()
    # Test destructive query rejection
    res = await server.call_tool("execute_sql", {"query": "DROP TABLE important_data"})
    assert res.isError is True
    assert "Destructive" in res.content[0].text


@pytest.mark.asyncio
async def test_mcp_manager_builtin_discovery():
    tools = MCPManager.get_builtin_tools()
    tool_names = [t.name for t in tools]
    assert "execute_sql" in tool_names
    assert "list_tables" in tool_names
    assert "search_catalog" in tool_names


def test_truncate_output_safety():
    short_text = "Hello world"
    assert _truncate_output(short_text) == short_text

    long_text = "a" * (60 * 1024)  # 60KB
    truncated = _truncate_output(long_text)
    assert "[TRUNCATED:" in truncated
    assert len(truncated.encode("utf-8")) < 55 * 1024
