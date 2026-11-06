def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def test_db_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Open the connection and report whether it works.

    USE_COMPUTE, not BROWSE: this decrypts the stored credentials and makes a
    real connection to the remote database on the caller's behalf.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    success, message = test_connection(conn)
    return PingResponse(success=success, message=message)
