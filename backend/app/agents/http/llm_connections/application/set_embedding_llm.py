def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def set_embedding_llm(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Mark a single LLM connection as the embedding provider (exclusive toggle).

    Admin, not EDIT on the one connection: the toggle is workspace-wide, and it
    clears the flag on every other connection, including ones the caller may
    hold no grant on at all. It also decides which provider every future
    embedding — and so the content of every indexed document — is sent to.
    """
    guard.require_workspace_admin("Choosing the embedding model")
    workspace_id = guard.workspace_id
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    db.query(LLMConnection).filter(LLMConnection.workspace_id == workspace_id).update({LLMConnection.use_for_embedding: False})
    conn.use_for_embedding = True
    try:
        db.commit()
        db.refresh(conn)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to set embedding LLM connection: {exc}") from exc
    return _to_response(conn)
