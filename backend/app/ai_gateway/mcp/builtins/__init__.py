"""Native Built-in MCP Servers for CompassX AI Gateway."""

from app.ai_gateway.mcp.builtins.base_builtin import BaseBuiltinMCPServer
from app.ai_gateway.mcp.builtins.sql_warehouse_mcp import SQLWarehouseMCPServer
from app.ai_gateway.mcp.builtins.catalog_search_mcp import CatalogSearchMCPServer
from app.ai_gateway.mcp.builtins.notebook_manager_mcp import NotebookManagerMCPServer
from app.ai_gateway.mcp.builtins.dashboard_manager_mcp import DashboardManagerMCPServer

BUILTIN_MCP_SERVERS: dict[str, BaseBuiltinMCPServer] = {
    "compassx_sql_warehouse": SQLWarehouseMCPServer(),
    "compassx_catalog_search": CatalogSearchMCPServer(),
    "compassx_notebook_manager": NotebookManagerMCPServer(),
    "compassx_dashboard_manager": DashboardManagerMCPServer(),
}

__all__ = [
    "BaseBuiltinMCPServer",
    "SQLWarehouseMCPServer",
    "CatalogSearchMCPServer",
    "NotebookManagerMCPServer",
    "DashboardManagerMCPServer",
    "BUILTIN_MCP_SERVERS",
]
