def _bind():
    import app.ai_gateway.http.providers.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get AI Provider details by ID."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_provider_response(provider)
