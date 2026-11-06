def _bind():
    import app.agents.http.external_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_external_connections(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the external connections the caller may see.

    Queried here rather than through ``svc.list_connections``, which also
    returns rows with a null workspace to every workspace.
    """
    q = db.query(ExternalConnection).filter(
        ExternalConnection.workspace_id == guard.workspace_id
    )
    if status_filter:
        q = q.filter(ExternalConnection.status == status_filter)
    rows = q.order_by(ExternalConnection.created_at.desc()).all()
    return [_to_response(c) for c in visible_connections(guard, rows)]
