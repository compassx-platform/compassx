def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_db_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a connection.

    MANAGE: it takes away access for everyone granted on it, and the stored
    credentials go with it.
    """
    conn = _get_or_404(sys_db, connection_id, guard, Privilege.MANAGE)
    sys_db.delete(conn)
    sys_db.commit()
    sync_agent_db_connection(connection_id, None, [], db)
