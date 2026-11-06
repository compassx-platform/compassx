def _bind():
    import app.agents.http.external_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_external_connection(
    connection_id: str,
    payload: ExternalConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Change an external connection.

    EDIT: ``base_url`` decides which host the stored credential is sent to, so
    this can redirect an existing grant at a different system.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    try:
        updated = svc.update_connection(db, conn.id, payload, workspace_id=guard.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _to_response(updated)
