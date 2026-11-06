def _bind():
    import app.agents.http.artifacts.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_changes(
    request: Request,
    agent_id: int,
    session_id: int,
    step_id: int | None = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return change records for this session, optionally filtered by plan step (G5)."""
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    records = get_changes_for_session(db, session_id, step_id=step_id)
    # Enrich with resolved URL
    for r in records:
        r["url"] = _resolve_asset_url(r["full_name"], r["object_type"])
    return records
