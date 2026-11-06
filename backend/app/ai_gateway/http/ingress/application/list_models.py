def _bind():
    import app.ai_gateway.http.ingress.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_models(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI-compatible list models endpoint."""
    workspace_id, caller_type, caller_id = _resolve_caller_and_workspace(request)
    query = db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)  # noqa: E712
    if workspace_id:
        query = query.filter((AIModelEndpoint.workspace_id == workspace_id) | (AIModelEndpoint.workspace_id.is_(None)))
    endpoints = query.all()

    if not endpoints:
        # Check if an active AIProvider exists in this workspace and seed initial endpoints
        prov_query = db.query(AIProvider).filter(AIProvider.is_active == True)
        if workspace_id:
            prov_query = prov_query.filter((AIProvider.workspace_id == workspace_id) | (AIProvider.workspace_id.is_(None)))
        provider = prov_query.first()
        if provider:
            seeded = []
            default_models = ["gpt-5.4-mini", "gpt-5.6-sol"]
            for idx, m_name in enumerate(default_models):
                ep = AIModelEndpoint(
                    workspace_id=workspace_id,
                    name=m_name,
                    provider_id=provider.id,
                    upstream_model_name=m_name,
                    is_active=True,
                    is_default=(idx == 0),
                )
                db.add(ep)
                seeded.append(ep)
            try:
                db.commit()
                endpoints = seeded
            except Exception:
                db.rollback()

    model_items = [
        ModelItem(
            id=ep.name,
            provider_type=getattr(ep.provider.provider_type, "value", ep.provider.provider_type) if ep.provider else "unknown",
            is_default=ep.is_default,
            use_for_embedding=ep.use_for_embedding,
        )
        for ep in endpoints
    ]
    return ModelListResponse(data=model_items)
