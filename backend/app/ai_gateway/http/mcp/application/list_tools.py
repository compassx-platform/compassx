def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def list_tools(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all aggregated tools available in the workspace (built-ins + external servers)."""
    ws_id = _get_workspace_id(request)
    return await MCPManager.list_all_tools_for_workspace(db, ws_id)
