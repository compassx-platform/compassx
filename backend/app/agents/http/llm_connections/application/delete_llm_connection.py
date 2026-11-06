def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_llm_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a model connection.

    MANAGE: every agent bound to it stops working, and the grants go with it.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.MANAGE)
    db.delete(conn)
    db.commit()
