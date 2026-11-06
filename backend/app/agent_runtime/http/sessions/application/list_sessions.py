def _bind():
    import app.agent_runtime.http.sessions.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_sessions(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List all agent runtime sessions for the workspace."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = workspace_id or (str(ctx.workspace_id) if ctx else None)
    return agent_runtime_service.list_sessions(workspace_id=ws_id)
