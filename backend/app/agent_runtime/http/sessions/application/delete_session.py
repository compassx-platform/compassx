def _bind():
    import app.agent_runtime.http.sessions.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_session(session_id: str):
    """Delete an agent runtime session."""
    ok = agent_runtime_service.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"deleted": True, "session_id": session_id}
