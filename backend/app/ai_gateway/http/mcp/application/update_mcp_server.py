def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update MCP server configuration and refresh tools."""
    ws_id = _get_workspace_id(request)
    server, _, _ = _resolve_mcp_server(server_id, db, ws_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    if body.catalog_name is not None:
        server.catalog_name = body.catalog_name
    if body.schema_name is not None:
        server.schema_name = body.schema_name
    if body.name is not None:
        server.name = body.name
    if body.description is not None:
        server.description = body.description
    if body.server_type is not None:
        server.server_type = body.server_type.value if hasattr(body.server_type, "value") else str(body.server_type)
    if body.endpoint_url is not None:
        server.endpoint_url = body.endpoint_url
    if body.auth_headers is not None:
        server.auth_config_enc = encrypt_field(json.dumps(body.auth_headers)) if body.auth_headers else None
    if body.command is not None:
        server.command = body.command
    if body.env_vars is not None:
        server.env_vars_enc = encrypt_field(json.dumps(body.env_vars)) if body.env_vars else None
    if body.is_enabled is not None:
        server.is_enabled = body.is_enabled

    db.commit()
    db.refresh(server)

    # Sync tools if connection changed
    try:
        if server.server_type in ("remote_sse", "subprocess") and (server.endpoint_url or server.command):
            await MCPManager.sync_server_tools(db, server)
            db.refresh(server)
    except Exception as sync_err:
        logger.warning("Tools sync for updated MCP server '%s' warning: %s", server.name, sync_err)

    return _to_mcp_response(server)
