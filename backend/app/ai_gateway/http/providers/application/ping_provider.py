def _bind():
    import app.ai_gateway.http.providers.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def ping_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Test connectivity to an external AI Provider."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    plain_key = None
    if provider.api_key_enc:
        try:
            plain_key = decrypt_field(provider.api_key_enc)
        except Exception:
            plain_key = None
    adapter = get_provider_adapter(provider.provider_type)
    creds = ProviderCredentials(
        provider_type=provider.provider_type,
        api_key=plain_key,
        base_url=provider.base_url,
        config=provider.config or {},
    )

    start_time = time.time()
    try:
        success, message, models = await adapter.ping(creds)
    except Exception as e:
        logger.exception("Ping error for provider %s: %s", provider.id, e)
        success = False
        message = f"Ping failed: {str(e)}"
        models = []

    latency_ms = int((time.time() - start_time) * 1000)

    return AIProviderPingResponse(
        success=success,
        message=message,
        latency_ms=latency_ms,
        available_models=models,
    )
