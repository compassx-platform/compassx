def _bind():
    import app.agents.http.git_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_git_connection(
    request: Request,
    connection_id: int,
    body: GitConnectionUpdate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Change a git connection.

    EDIT: it can repoint the connection at a different organization or swap
    the PAT, which every existing grantee then acts with.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    data = body.model_dump(exclude_none=True)
    if "pat" in data:
        pat = data.pop("pat")
        conn.pat_enc = encrypt_field(pat) if pat else None
    for field, value in data.items():
        setattr(conn, field, value)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)
