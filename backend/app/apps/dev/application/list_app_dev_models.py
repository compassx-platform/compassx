def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def list_app_dev_models(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List available AI models for the app's workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    from app.database import AccountSessionLocal
    from app.ai_gateway.models.provider import AIModelEndpoint, AIProvider

    with AccountSessionLocal() as acc_db:
        ws_id = str(app.workspace_id) if app.workspace_id else None
        query = acc_db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)
        if ws_id:
            query = query.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
        endpoints = query.all()

        if not endpoints:
            prov_query = acc_db.query(AIProvider).filter(AIProvider.is_active == True)
            if ws_id:
                prov_query = prov_query.filter((AIProvider.workspace_id == ws_id) | (AIProvider.workspace_id.is_(None)))
            provider = prov_query.first()
            if provider:
                default_models = ["gpt-5.4-mini", "gpt-5.6-sol"]
                seeded = []
                for idx, m_name in enumerate(default_models):
                    ep = AIModelEndpoint(
                        workspace_id=ws_id,
                        name=m_name,
                        provider_id=provider.id,
                        upstream_model_name=m_name,
                        is_active=True,
                        is_default=(idx == 0),
                    )
                    acc_db.add(ep)
                    seeded.append(ep)
                try:
                    acc_db.commit()
                    endpoints = seeded
                except Exception:
                    acc_db.rollback()

        return [
            {
                "id": ep.name,
                "name": ep.name,
                "is_default": ep.is_default,
                "provider": ep.provider.name if ep.provider else "azure",
            }
            for ep in endpoints
        ]
