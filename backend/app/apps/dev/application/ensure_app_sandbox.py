def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def ensure_app_sandbox(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Idempotently ensure dev sandbox is running for this app, returning live progress or ready instance."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    unified_reaper_service.touch_app_activity(app.id)
    spec = _build_app_sandbox_spec(app)
    instance = sandbox_service.ensure_sandbox(spec)
    if instance.status in (SandboxStatus.READY, SandboxStatus.RUNNING):
        _sync_agent_login(app)
    return instance
