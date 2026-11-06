def _bind():
    import app.agents.http.streams.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_active_streams(
    request: Request,
    kind: str | None = Query(default=None, pattern="^agent$"),
    agent_id: int | None = None,
    session_id: int | None = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the running streams the caller may see."""
    streams = stream_registry.list(
        kind=kind,
        agent_id=agent_id,
        session_id=session_id,
        workspace_id=guard.workspace_id,
    )
    visible = [s for s in streams if s.get("agent_id") is not None]
    return {
        "streams": guard.filter(
            Privilege.BROWSE, visible, lambda s: Securable.agent(str(s["agent_id"]))
        ),
    }
