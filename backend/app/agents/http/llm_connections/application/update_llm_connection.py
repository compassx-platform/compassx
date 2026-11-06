def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_llm_connection(
    request: Request,
    connection_id: int,
    body: LLMConnectionUpdate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Change a model connection.

    EDIT: this can repoint the connection at a different provider or key while
    everyone granted on it keeps calling it.
    """
    workspace_id = guard.workspace_id
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    data = body.model_dump(exclude_none=True)
    if data.get("use_for_embedding"):
        db.query(LLMConnection).filter(LLMConnection.workspace_id == workspace_id).update({LLMConnection.use_for_embedding: False})
    if "api_key" in data:
        conn.api_key_enc = encrypt_field(data.pop("api_key"))
    
    # Check if cost was updated to set metadata
    has_cost_update = "input_cost_per_1k_tokens" in data or "output_cost_per_1k_tokens" in data or "cost_currency" in data
    if has_cost_update:
        username = str(guard.principal.id)
        conn.cost_configured_at = datetime.now(timezone.utc)
        conn.cost_configured_by = username

    for field, value in data.items():
        setattr(conn, field, value)
    try:
        db.commit()
        db.refresh(conn)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to update LLM connection: {exc}") from exc
    return _to_response(conn)
