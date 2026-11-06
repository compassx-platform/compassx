def _bind():
    import app.ai_gateway.http.endpoints.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_endpoint(
    body: AIModelEndpointCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Create a new AI Model Endpoint."""
    ws_id = _get_workspace_id(request)

    # Verify provider exists
    provider = db.query(AIProvider).filter(AIProvider.id == body.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail=f"Provider with ID {body.provider_id} not found.")

    # Check unique name
    existing_query = db.query(AIModelEndpoint).filter(AIModelEndpoint.name == body.name)
    if ws_id:
        existing_query = existing_query.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Endpoint with alias '{body.name}' already exists.")

    if body.is_default and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"is_default": False})

    if body.use_for_embedding and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"use_for_embedding": False})

    endpoint = AIModelEndpoint(
        workspace_id=ws_id,
        name=body.name,
        provider_id=body.provider_id,
        upstream_model_name=body.upstream_model_name,
        fallback_endpoint_ids=body.fallback_endpoint_ids,
        timeout_s=body.timeout_s,
        max_tokens=body.max_tokens,
        temperature_default=body.temperature_default,
        rate_limit_rpm=body.rate_limit_rpm,
        rate_limit_tpm=body.rate_limit_tpm,
        input_cost_per_1k_tokens=body.input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=body.output_cost_per_1k_tokens,
        cost_currency=body.cost_currency,
        use_for_embedding=body.use_for_embedding,
        is_default=body.is_default,
        guardrail_config=body.guardrail_config,
        is_active=body.is_active,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)
