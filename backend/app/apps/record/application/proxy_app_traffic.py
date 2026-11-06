def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

async def proxy_app_traffic(
    app_id: str,
    path: str,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """Proxy HTTP traffic to the active app container or process."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    unified_reaper_service.touch_app_activity(app_id)
    return await app_runner_service.proxy_request(app, path, request)
