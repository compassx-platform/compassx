def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_omnigent_mcp_config(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Return unified MCP server configurations formatted for Claude Code, OpenCode, Antigravity, and Codex harnesses."""
    ws_id = _get_workspace_id(request)
    return build_mcp_configs_from_gateway(db=db, workspace_id=ws_id)
