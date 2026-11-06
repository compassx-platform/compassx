def _bind():
    import app.agents.http.artifacts.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_change_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    change_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return a single change record with full before/after content (G5).

    The response is the previous and new definition of a catalog object, so a
    caller who could reach this without BROWSE on the agent would be reading
    object content through the change log.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    record = get_change_record(db, change_id)
    if not record:
        raise HTTPException(404, f"Change {change_id} not found")
    record["url"] = _resolve_asset_url(record["full_name"], record["object_type"])
    return record
