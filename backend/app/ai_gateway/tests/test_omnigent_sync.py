"""Unit tests for Omnigent & Harness MCP configuration synchronization."""

import json
import os
from unittest.mock import MagicMock
from app.ai_gateway.models.mcp import MCPServer
from app.ai_gateway.mcp.omnigent_sync import (
    build_mcp_configs_from_gateway,
    sync_workspace_mcp_configs,
    get_mcp_sync_shell_script,
)


def test_build_mcp_configs_from_gateway_native_only():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []

    configs = build_mcp_configs_from_gateway(db=mock_db)
    # Native built-ins: sql_warehouse, catalog_search, notebook_manager, dashboard_manager
    assert configs["servers_count"] == 4
    assert "compassx_sql_warehouse" in configs["mcpServers"]
    assert "compassx_catalog_search" in configs["mcpServers"]
    assert "compassx_notebook_manager" in configs["mcpServers"]
    assert "compassx_dashboard_manager" in configs["mcpServers"]
    assert "mcp" in configs["opencode"]
    assert "mcpServers" in configs["claude"]


def test_build_mcp_configs_with_external_servers():
    mock_server_sse = MagicMock(spec=MCPServer)
    mock_server_sse.name = "EAM_MCP"
    mock_server_sse.server_type = "remote_sse"
    mock_server_sse.endpoint_url = "https://eam-dev.135.13.180.167.nip.io/mcp/sse"
    mock_server_sse.command = None
    mock_server_sse.auth_config_enc = None
    mock_server_sse.env_vars_enc = None
    mock_server_sse.is_enabled = True

    mock_server_cmd = MagicMock(spec=MCPServer)
    mock_server_cmd.name = "CLI_TOOL"
    mock_server_cmd.server_type = "subprocess"
    mock_server_cmd.endpoint_url = None
    mock_server_cmd.command = "python -m my_mcp_module"
    mock_server_cmd.auth_config_enc = None
    mock_server_cmd.env_vars_enc = None
    mock_server_cmd.is_enabled = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_server_sse, mock_server_cmd]

    configs = build_mcp_configs_from_gateway(db=mock_db)
    # 4 native built-ins + 2 external servers = 6
    assert configs["servers_count"] == 6

    # Native tools
    assert "compassx_sql_warehouse" in configs["mcpServers"]
    assert "compassx_catalog_search" in configs["mcpServers"]

    # Universal
    assert "EAM_MCP" in configs["mcpServers"]
    assert configs["mcpServers"]["EAM_MCP"]["url"] == "https://eam-dev.135.13.180.167.nip.io/mcp/sse"
    assert configs["mcpServers"]["EAM_MCP"]["type"] == "sse"

    assert "CLI_TOOL" in configs["mcpServers"]
    assert configs["mcpServers"]["CLI_TOOL"]["command"] == "python"
    assert configs["mcpServers"]["CLI_TOOL"]["args"] == ["-m", "my_mcp_module"]

    # OpenCode
    assert configs["opencode"]["mcp"]["EAM_MCP"]["type"] == "remote"
    assert configs["opencode"]["mcp"]["EAM_MCP"]["url"] == "https://eam-dev.135.13.180.167.nip.io/mcp/sse"

    # Claude
    assert "EAM_MCP" in configs["claude"]["mcpServers"]
    assert "compassx_sql_warehouse" in configs["claude"]["mcpServers"]


def test_sync_workspace_mcp_configs(tmp_path):
    mock_server = MagicMock(spec=MCPServer)
    mock_server.name = "EAM_MCP"
    mock_server.server_type = "remote_sse"
    mock_server.endpoint_url = "https://eam-dev.135.13.180.167.nip.io/mcp/sse"
    mock_server.command = None
    mock_server.auth_config_enc = None
    mock_server.env_vars_enc = None
    mock_server.is_enabled = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_server]

    ws_dir = str(tmp_path / "test_workspace")
    os.makedirs(ws_dir, exist_ok=True)

    ok = sync_workspace_mcp_configs(ws_dir, db=mock_db)
    assert ok is True

    # Verify generated files
    assert os.path.exists(os.path.join(ws_dir, ".mcp.json"))
    assert os.path.exists(os.path.join(ws_dir, "mcp.json"))
    assert os.path.exists(os.path.join(ws_dir, "opencode.json"))
    assert os.path.exists(os.path.join(ws_dir, ".gemini", "settings.json"))
    assert os.path.exists(os.path.join(ws_dir, ".cursor", "mcp.json"))

    with open(os.path.join(ws_dir, ".mcp.json")) as f:
        data = json.load(f)
        assert "EAM_MCP" in data["mcpServers"]
        assert "compassx_sql_warehouse" in data["mcpServers"]
        assert "compassx_catalog_search" in data["mcpServers"]
        assert "compassx_notebook_manager" in data["mcpServers"]
        assert "compassx_dashboard_manager" in data["mcpServers"]


def test_get_mcp_sync_shell_script():
    snippet = get_mcp_sync_shell_script("https://compassx.example.com")
    assert "python3 -c" in snippet
    assert "compassx.example.com" in snippet
    assert "opencode.json" in snippet
    assert ".claude.json" in snippet
