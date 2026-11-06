def _bind():
    import app.agent_runtime.http.sessions.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_session(request: Request, body: CreateAgentSessionRequest):
    """Create a new agent runtime session bound to a compute sandbox."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = str(ctx.workspace_id) if ctx else None
    try:
        return agent_runtime_service.create_session(body, workspace_id=ws_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")
