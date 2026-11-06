def _bind():
    import app.agents.http.streams.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def cancel_stream(
    request: Request,
    stream_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Stop a running turn.

    EXECUTE, the privilege that started it: whoever may run the agent may stop
    a run of it, and a runaway turn only its starter can kill is worse than one
    stopped by a colleague.
    """
    _authorized_stream(stream_id, guard, db, Privilege.EXECUTE)
    stream_registry.cancel(stream_id)
    return {"ok": True}
