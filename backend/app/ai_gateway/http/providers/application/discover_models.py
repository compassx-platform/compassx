def _bind():
    import app.ai_gateway.http.providers.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def discover_models(
    body: AIDiscoverModelsRequest,
    request: Request,
):
    """Test connection and discover available models from provider credentials without saving."""
    adapter = get_provider_adapter(body.provider_type)
    creds = ProviderCredentials(
        provider_type=body.provider_type,
        api_key=body.api_key,
        base_url=body.base_url,
        config=body.config or {},
    )

    start_time = time.time()
    try:
        success, message, models = await adapter.ping(creds)
    except Exception as e:
        logger.exception("Error discovering models for provider %s: %s", body.provider_type, e)
        success = False
        message = f"Discovery error: {str(e)}"
        models = []

    latency_ms = int((time.time() - start_time) * 1000)

    return AIProviderPingResponse(
        success=success,
        message=message,
        latency_ms=latency_ms,
        available_models=models,
    )
