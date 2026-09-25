"""Unit tests for standard Model Context Protocol (MCP) SSE Server and JSON-RPC processing."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai_gateway.mcp.sse_server import (
    MCPServerSession,
    MCPSessionManager,
    process_mcp_jsonrpc_message,
)


@pytest.mark.asyncio
async def test_mcp_session_manager():
    manager = MCPSessionManager()
    session = await manager.create_session(server_filter="compassx_sql_warehouse")
    assert session.session_id is not None
    assert session.server_filter == "compassx_sql_warehouse"
    assert session.is_active is True

    fetched = manager.get_session(session.session_id)
    assert fetched == session

    manager.close_session(session.session_id)
    assert manager.get_session(session.session_id) is None


@pytest.mark.asyncio
async def test_process_mcp_initialize():
    mock_db = MagicMock()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    res = await process_mcp_jsonrpc_message(req, session=None, db=mock_db)
    assert res["jsonrpc"] == "2.0"
    assert res["id"] == 1
    assert res["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in res["result"]["capabilities"]
    assert res["result"]["serverInfo"]["name"] == "compassx-ai-gateway"


@pytest.mark.asyncio
async def test_process_mcp_ping():
    mock_db = MagicMock()
    req = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "ping",
    }
    res = await process_mcp_jsonrpc_message(req, session=None, db=mock_db)
    assert res["jsonrpc"] == "2.0"
    assert res["id"] == 42
    assert res["result"] == {}


@pytest.mark.asyncio
async def test_process_mcp_tools_list_all():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []

    req = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/list",
        "params": {},
    }
    res = await process_mcp_jsonrpc_message(req, session=None, db=mock_db)
    assert res["jsonrpc"] == "2.0"
    assert res["id"] == 100
    tool_names = [t["name"] for t in res["result"]["tools"]]
    assert "search_catalog" in tool_names
    assert "execute_sql" in tool_names or "list_tables" in tool_names
    assert "notebook_manage" in tool_names or "create_notebook" in tool_names
    assert "dashboard_manage" in tool_names or "create_dashboard" in tool_names


@pytest.mark.asyncio
async def test_process_mcp_tools_list_server_filtered():
    mock_db = MagicMock()
    session = MCPServerSession(session_id="test-1", server_filter="compassx_notebook_manager")

    req = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/list",
        "params": {},
    }
    res = await process_mcp_jsonrpc_message(req, session=session, db=mock_db)
    assert res["jsonrpc"] == "2.0"
    tool_names = [t["name"] for t in res["result"]["tools"]]
    assert "notebook_manage" in tool_names
    assert "search_catalog" not in tool_names


@pytest.mark.asyncio
async def test_process_mcp_tools_call_success():
    mock_db = MagicMock()
    req = {
        "jsonrpc": "2.0",
        "id": 200,
        "method": "tools/call",
        "params": {
            "name": "search_catalog",
            "arguments": {"query": "test"},
        },
    }
    with patch("app.ai_gateway.mcp.proxy.MCPExecutionProxy.execute_tool") as mock_exec:
        from app.ai_gateway.schemas.mcp import MCPToolCallResponse
        mock_exec.return_value = MCPToolCallResponse(
            success=True,
            server_name="compassx_catalog_search",
            tool_name="search_catalog",
            result={"results": [{"table": "users"}]},
            error=None,
        )
        res = await process_mcp_jsonrpc_message(req, session=None, db=mock_db)
        assert res["id"] == 200
        assert res["result"]["isError"] is False
        assert "users" in res["result"]["content"][0]["text"]
