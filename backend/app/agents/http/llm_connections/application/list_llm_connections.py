def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_llm_connections(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the model connections the caller may see.

    The API key comes back masked, never in full — the stored value is only
    decrypted to compute the mask and when a call is actually made.
    """
    rows = (
        db.query(LLMConnection)
        .filter(LLMConnection.workspace_id == guard.workspace_id)
        .order_by(LLMConnection.name)
        .all()
    )
    return [_to_response(r) for r in visible_connections(guard, rows)]
