"""AI Gateway MCP module exports."""

from app.ai_gateway.mcp.types import (
    MCPTool,
    MCPToolResult,
    MCPToolContent,
    JSONRPCRequest,
    JSONRPCResponse,
)
from app.ai_gateway.mcp.client import MCPClient
from app.ai_gateway.mcp.manager import MCPManager
from app.ai_gateway.mcp.proxy import MCPExecutionProxy
from app.ai_gateway.mcp.builtins import (
    BUILTIN_MCP_SERVERS,
    BaseBuiltinMCPServer,
    SQLWarehouseMCPServer,
    CatalogSearchMCPServer,
    NotebookManagerMCPServer,
    DashboardManagerMCPServer,
)
from app.ai_gateway.mcp.sse_server import (
    handle_mcp_sse_stream,
    mcp_session_manager,
    process_mcp_jsonrpc_message,
)
from app.ai_gateway.mcp.omnigent_sync import (
    build_mcp_configs_from_gateway,
    sync_workspace_mcp_configs,
    get_mcp_sync_shell_script,
)

__all__ = [
    "MCPTool",
    "MCPToolResult",
    "MCPToolContent",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "MCPClient",
    "MCPManager",
    "MCPExecutionProxy",
    "BUILTIN_MCP_SERVERS",
    "BaseBuiltinMCPServer",
    "SQLWarehouseMCPServer",
    "CatalogSearchMCPServer",
    "NotebookManagerMCPServer",
    "DashboardManagerMCPServer",
    "handle_mcp_sse_stream",
    "mcp_session_manager",
    "process_mcp_jsonrpc_message",
    "build_mcp_configs_from_gateway",
    "sync_workspace_mcp_configs",
    "get_mcp_sync_shell_script",
]
