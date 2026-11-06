def _bind():
    import app.ai_gateway.http.providers.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_providers(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all AI Providers accessible in the current workspace."""
    ws_id = _get_workspace_id(request)
    query = db.query(AIProvider)
    if ws_id:
        query = query.filter((AIProvider.workspace_id == ws_id) | (AIProvider.workspace_id.is_(None)))
    providers = query.order_by(AIProvider.name).all()
    return [_to_provider_response(p) for p in providers]
