def _bind():
    import app.ai_gateway.http.providers.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_provider(
    body: AIProviderCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Create a new AI Provider configuration."""
    ws_id = _get_workspace_id(request)

    # Check name duplicate in workspace
    existing_query = db.query(AIProvider).filter(AIProvider.name == body.name)
    if ws_id:
        existing_query = existing_query.filter((AIProvider.workspace_id == ws_id) | (AIProvider.workspace_id.is_(None)))
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Provider with name '{body.name}' already exists.")

    p_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    api_key_enc = encrypt_field(body.api_key) if body.api_key else None
    actor = request.headers.get("X-User-Email") or request.headers.get("X-User-Id") or "system"
    base_url = (body.base_url or "").strip() or None
    if not base_url and p_type == "grok":
        base_url = "https://api.x.ai/v1"
    provider = AIProvider(
        workspace_id=ws_id,
        catalog_name=body.catalog_name,
        schema_name=body.schema_name,
        name=body.name,
        provider_type=p_type,
        api_key_enc=api_key_enc,
        base_url=base_url,
        config=body.config,
        is_active=body.is_active,
        created_by=body.created_by or actor,
    )
    db.add(provider)
    db.flush()
    _sync_provider_endpoints(db, provider, body.allowed_models, ws_id)
    db.commit()
    db.refresh(provider)
    return _to_provider_response(provider)
