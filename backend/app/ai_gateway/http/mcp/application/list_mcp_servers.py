def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_mcp_servers(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List registered MCP servers (both built-in native and remote/subprocess) in the current workspace."""
    ws_id = _get_workspace_id(request)
    base_url = _resolve_base_url(request)

    results: list[MCPServerResponse] = []
    # 1. Native Built-in servers
    for b_name, b_inst in BUILTIN_MCP_SERVERS.items():
        tool_list = [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema,
            }
            for t in b_inst.list_tools()
        ]
        results.append(
            MCPServerResponse(
                id=abs(hash(b_name)) % 100000 + 1,
                workspace_id=ws_id,
                catalog_name="system",
                schema_name="ai",
                full_name=f"system.ai.{b_name}",
                name=b_name,
                description=b_inst.description,
                server_type="native",
                endpoint_url=f"{base_url}/api/v1/ai-gateway/mcp/servers/{b_name}/sse",
                has_auth=False,
                command=None,
                is_enabled=True,
                created_by="system",
                cached_tools=tool_list,
                last_synced_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    # 2. Database registered servers
    query = db.query(MCPServer)
    if ws_id:
        query = query.filter((MCPServer.workspace_id == ws_id) | (MCPServer.workspace_id.is_(None)))
    servers = query.order_by(MCPServer.name).all()
    for s in servers:
        if not any(r.name == s.name for r in results):
            results.append(_to_mcp_response(s, base_url))

    return results
