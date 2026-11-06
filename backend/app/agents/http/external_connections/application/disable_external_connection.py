def _bind():
    import app.agents.http.external_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def disable_external_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Take a connection out of service.

    EDIT rather than MANAGE: it is reversible and nothing is destroyed, but it
    stops every agent using it, so it is not a read.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    try:
        updated = svc.disable_connection(db, conn.id, workspace_id=guard.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _to_response(updated)
