def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def introspect_schema(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the tables and columns of the remote database.

    USE_COMPUTE: the response is content read out of the remote system, not
    metadata CompassX holds about the connection.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    try:
        tables = get_schema(build_engine(conn))
    except Exception as exc:
        raise HTTPException(400, f"Schema introspection failed: {exc}")
    return SchemaIntrospectionResponse(tables=tables)
