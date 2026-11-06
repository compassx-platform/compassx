def _bind():
    import app.agents.http.artifacts.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def reject_change_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    change_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Reject a change — re-applies before content and creates a new revert record (D20).

    EXECUTE: this writes the previous content back to the catalog object, so
    it is the agent acting again, under the same delegation.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    result = reject_change(db, change_id, session_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Reject failed"))
    return result
