def _bind():
    import app.agents.http.artifacts.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def accept_change_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    change_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Accept a change record — sets status to 'accepted', no further write (D20).

    EXECUTE, not BROWSE: accepting is a review decision that settles what the
    agent did, and it takes the same privilege as having run the turn.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    result = accept_change(db, change_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Accept failed"))
    return result
