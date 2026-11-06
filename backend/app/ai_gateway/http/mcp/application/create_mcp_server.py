def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def create_mcp_server(
    body: MCPServerCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Register a new MCP server (Native, Remote SSE, or Subprocess) and auto-sync tools."""
    ws_id = _get_workspace_id(request)

    existing_query = db.query(MCPServer).filter(MCPServer.name == body.name)
    if ws_id:
        existing_query = existing_query.filter((MCPServer.workspace_id == ws_id) | (MCPServer.workspace_id.is_(None)))
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"MCP server '{body.name}' already registered.")

    auth_enc = encrypt_field(json.dumps(body.auth_headers)) if body.auth_headers else None
    env_enc = encrypt_field(json.dumps(body.env_vars)) if body.env_vars else None
    s_type = body.server_type.value if hasattr(body.server_type, "value") else str(body.server_type)
    user_email = getattr(request.state, "user_email", None) or "system"

    server = MCPServer(
        workspace_id=ws_id,
        catalog_name=body.catalog_name,
        schema_name=body.schema_name,
        name=body.name,
        description=body.description,
        server_type=s_type,
        endpoint_url=body.endpoint_url,
        auth_config_enc=auth_enc,
        command=body.command,
        env_vars_enc=env_enc,
        is_enabled=body.is_enabled,
        created_by=user_email,
        cached_tools=[],
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    # Immediately sync tools from remote server
    try:
        if server.server_type in ("remote_sse", "subprocess") and (server.endpoint_url or server.command):
            await MCPManager.sync_server_tools(db, server)
            db.refresh(server)
    except Exception as sync_err:
        logger.warning("Initial tools discovery for MCP server '%s' completed with warning: %s", server.name, sync_err)

    return _to_mcp_response(server)
