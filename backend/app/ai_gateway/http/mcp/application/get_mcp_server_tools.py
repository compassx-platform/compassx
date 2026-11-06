def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def get_mcp_server_tools(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Retrieve the live tools list exposed by an MCP server (with real-time introspection and latency)."""
    import time

    start_time = time.perf_counter()
    ws_id = _get_workspace_id(request)
    db_server, builtin_name, builtin_inst = _resolve_mcp_server(server_id, db, ws_id)

    # Case 1: Built-in Native Servers
    if builtin_inst and builtin_name:
        tools = builtin_inst.list_tools()
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        tool_defs = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema,
            }
            for t in tools
        ]
        full_ref = f"system.ai.{builtin_name}"
        return {
            "success": True,
            "message": f"Successfully retrieved tools from native MCP server '{builtin_name}'",
            "latency_ms": latency_ms,
            "called_endpoint": f"/api/v1/ai-gateway/mcp/servers/{full_ref}/tools",
            "http_method": "GET",
            "mcp_method": "tools/list",
            "mcp_protocol": "JSON-RPC 2.0",
            "upstream_target": "compassx-internal-runtime",
            "server_id": builtin_name,
            "server_name": builtin_name,
            "server_full_name": full_ref,
            "server_type": "native",
            "endpoint_url": "compassx-internal-runtime",
            "tools_count": len(tool_defs),
            "tools": tool_defs,
            "raw_response": {
                "jsonrpc": "2.0",
                "result": {
                    "tools": tool_defs
                }
            }
        }

    # Case 2: Registered Database Servers (Remote SSE or Subprocess)
    if not db_server:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_id}' not found")

    server = db_server
    cat = server.catalog_name or "default"
    sch = server.schema_name or "default"
    full_ref = f"{cat}.{sch}.{server.name}"
    target = server.endpoint_url or server.command or "unknown"

    try:
        tools = await MCPManager.sync_server_tools(db, server)
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        tool_defs = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema,
            }
            for t in tools
        ]
        return {
            "success": True,
            "message": f"Successfully retrieved tools from MCP server '{server.name}' via {server.server_type.upper()}",
            "latency_ms": latency_ms,
            "called_endpoint": f"/api/v1/ai-gateway/mcp/servers/{full_ref}/tools",
            "http_method": "GET",
            "mcp_method": "tools/list",
            "mcp_protocol": "JSON-RPC 2.0",
            "upstream_target": target,
            "server_id": server.id,
            "server_name": server.name,
            "server_full_name": full_ref,
            "server_type": server.server_type,
            "endpoint_url": target,
            "tools_count": len(tool_defs),
            "tools": tool_defs,
            "raw_response": {
                "jsonrpc": "2.0",
                "result": {
                    "tools": tool_defs
                }
            }
        }
    except Exception as e:
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        logger.error("Error retrieving tools for MCP server %s: %s", server.name, e)
        return {
            "success": False,
            "message": f"Failed to retrieve tools: {str(e)}",
            "latency_ms": latency_ms,
            "called_endpoint": f"/api/v1/ai-gateway/mcp/servers/{full_ref}/tools",
            "http_method": "GET",
            "mcp_method": "tools/list",
            "mcp_protocol": "JSON-RPC 2.0",
            "upstream_target": target,
            "server_id": server.id,
            "server_name": server.name,
            "server_full_name": full_ref,
            "server_type": server.server_type,
            "endpoint_url": target,
            "tools_count": 0,
            "tools": [],
            "raw_response": {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        }
