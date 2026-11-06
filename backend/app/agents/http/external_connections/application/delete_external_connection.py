def _bind():
    import app.agents.http.external_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_external_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a connection and its stored credential.

    MANAGE: irreversible, and it revokes access for everyone granted on it.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.MANAGE)
    db.delete(conn)
    db.commit()
    return None
