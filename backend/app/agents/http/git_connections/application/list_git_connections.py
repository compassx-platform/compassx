def _bind():
    import app.agents.http.git_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_git_connections(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the git connections the caller may see.

    ``pat_configured`` is a boolean — the token itself is encrypted at rest and
    only decrypted when a call to the provider is made.
    """
    rows = (
        db.query(GitConnection)
        .filter(GitConnection.workspace_id == guard.workspace_id)
        .order_by(GitConnection.name)
        .all()
    )
    return [_to_response(r) for r in visible_connections(guard, rows)]
