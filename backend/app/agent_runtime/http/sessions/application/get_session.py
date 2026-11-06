def _bind():
    import app.agent_runtime.http.sessions.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_session(session_id: str):
    """Get an agent runtime session and its transcript."""
    sess = agent_runtime_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return sess
