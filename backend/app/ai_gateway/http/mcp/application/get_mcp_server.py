def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_mcp_server(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get MCP server details by ID or catalog.schema.name."""
    ws_id = _get_workspace_id(request)
    server, _, _ = _resolve_mcp_server(server_id, db, ws_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return _to_mcp_response(server)
