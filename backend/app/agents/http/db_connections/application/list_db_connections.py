def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_db_connections(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the database connections the caller may see.

    The response carries host, port, and database name but never the stored
    credentials, which are encrypted at rest and only decrypted when a query
    is actually run.
    """
    rows = (
        db.query(DBConnection)
        .filter(DBConnection.workspace_id == guard.workspace_id)
        .order_by(DBConnection.name)
        .all()
    )
    return [_to_response(r) for r in visible_connections(guard, rows)]
