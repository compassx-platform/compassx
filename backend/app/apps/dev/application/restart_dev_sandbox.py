def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def restart_dev_sandbox(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Restart dev sandbox: cleanly terminate and re-ensure compute via Sandbox engine."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    unified_reaper_service.touch_app_activity(app.id)

    try:
        sandbox_service.terminate_sandbox(f"dev-app-{app.id}")
    except Exception as e:
        logger.debug("Restart termination error for dev-app-%s: %s", app.id, e)

    spec = _build_app_sandbox_spec(app)
    instance = sandbox_service.ensure_sandbox(spec)
    if instance.status in (SandboxStatus.READY, SandboxStatus.RUNNING):
        _sync_agent_login(app, force=True)
    return {
        "app_id": app.id,
        "status": "active" if instance.status in (SandboxStatus.READY, SandboxStatus.RUNNING) else str(instance.status.value),
        "mode": instance.runtime_mode,
        "container_id": instance.container_id,
        "dev_port": instance.ports[0] if instance.ports else 8080,
        "endpoints": instance.endpoints,
        "sandbox_id": instance.id,
    }
