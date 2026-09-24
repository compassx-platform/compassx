"""Native Built-in MCP Servers."""

from app.ai_gateway.mcp.builtins.base_builtin import BaseBuiltinMCPServer
from app.ai_gateway.mcp.builtins.sql_warehouse_mcp import SQLWarehouseMCPServer
from app.ai_gateway.mcp.builtins.catalog_search_mcp import CatalogSearchMCPServer

BUILTIN_MCP_SERVERS: dict[str, BaseBuiltinMCPServer] = {
    "compassx_sql_warehouse": SQLWarehouseMCPServer(),
    "compassx_catalog_search": CatalogSearchMCPServer(),
}

__all__ = [
    "BaseBuiltinMCPServer",
    "SQLWarehouseMCPServer",
    "CatalogSearchMCPServer",
    "BUILTIN_MCP_SERVERS",
]
