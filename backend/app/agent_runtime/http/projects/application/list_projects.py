from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def list_projects(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List agent runtime projects for the workspace."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = workspace_id or (str(ctx.workspace_id) if ctx else None)
    return agent_runtime_service.list_projects(workspace_id=ws_id)
