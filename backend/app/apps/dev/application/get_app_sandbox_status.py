def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def get_app_sandbox_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get active sandbox and detailed stage progress for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    unified_reaper_service.touch_app_activity(app.id)
    instance = sandbox_service.find_active_sandbox(
        sandbox_id=f"dev-app-{app.id}",
        consumer_key=f"app_{app.id}",
        consumer_module="app",
    )
    if instance:
        instance = sandbox_service.get_sandbox(instance.id)
        return instance
    return {
        "id": f"dev-app-{app.id}",
        "consumer_key": f"app_{app.id}",
        "name": f"{app.name} (Dev Sandbox)",
        "consumer_module": "app",
        "status": "stopped",
        "endpoints": {},
        "progress": None,
    }
