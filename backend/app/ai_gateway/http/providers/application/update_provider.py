def _bind():
    import app.ai_gateway.http.providers.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_provider(
    provider_id: int,
    body: AIProviderUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update AI Provider configuration."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if body.name is not None:
        provider.name = body.name
    if body.provider_type is not None:
        provider.provider_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    if body.catalog_name is not None:
        provider.catalog_name = body.catalog_name
    if body.schema_name is not None:
        provider.schema_name = body.schema_name
    if body.api_key is not None:
        provider.api_key_enc = encrypt_field(body.api_key) if body.api_key else None
    if body.base_url is not None:
        provider.base_url = body.base_url
    if body.config is not None:
        provider.config = body.config
    if body.is_active is not None:
        provider.is_active = body.is_active
    if body.created_by is not None:
        provider.created_by = body.created_by

    _sync_provider_endpoints(db, provider, body.allowed_models, provider.workspace_id or _get_workspace_id(request))
    db.commit()
    db.refresh(provider)
    return _to_provider_response(provider)
