def _bind():
    import app.agents.http.artifacts.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def bulk_review_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    body: dict,  # {"action": "accept_all" | "reject_all"}
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Bulk accept or reject all pending changes for a session."""
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    action = body.get("action", "accept_all")
    if action not in ("accept_all", "reject_all"):
        raise HTTPException(400, "action must be 'accept_all' or 'reject_all'")
    return bulk_review_changes(db, session_id, action)
