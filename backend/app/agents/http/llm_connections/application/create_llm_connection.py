def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_llm_connection(
    request: Request,
    body: LLMConnectionCreate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Register a model provider.

    Admin, for the same reason as a database connection: it stores a credential
    that anyone later granted USE_COMPUTE can spend against.
    """
    guard.require_workspace_admin("Creating an LLM connection")
    workspace_id = guard.workspace_id
    if body.use_for_embedding:
        db.query(LLMConnection).filter(LLMConnection.workspace_id == workspace_id).update({LLMConnection.use_for_embedding: False})

    username = str(guard.principal.id)

    conn = LLMConnection(
        workspace_id=workspace_id,
        name=body.name,
        provider=body.provider,
        model_name=body.model_name,
        api_key_enc=encrypt_field(body.api_key) if body.api_key else None,
        base_url=body.base_url,
        timeout_s=body.timeout_s,
        max_tokens=body.max_tokens,
        config=body.config,
        is_fallback=body.is_fallback,
        use_for_embedding=body.use_for_embedding,
        input_cost_per_1k_tokens=body.input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=body.output_cost_per_1k_tokens,
        cost_currency=body.cost_currency or "USD",
        cost_configured_at=datetime.now(timezone.utc) if body.input_cost_per_1k_tokens is not None else None,
        cost_configured_by=username if body.input_cost_per_1k_tokens is not None else None,
    )
    db.add(conn)
    try:
        db.commit()
        db.refresh(conn)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to save LLM connection: {exc}") from exc
    guard.claim_ownership(Securable.connection(str(conn.id)))
    return _to_response(conn)
