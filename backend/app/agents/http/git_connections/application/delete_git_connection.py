def _bind():
    import app.agents.http.git_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_git_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a git connection.

    MANAGE: it revokes access for everyone granted on it and discards the PAT.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.MANAGE)
    db.delete(conn)
    db.commit()
