def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def suspend_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Suspend dev sandbox (scale compute to 0 replicas, keep storage intact)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    db.expunge(app)
    db.close()

    try:
        sandbox_service.suspend_sandbox(f"dev-app-{app.id}")
    except Exception:
        pass

    try:
        active_sb = sandbox_service.find_active_sandbox(consumer_key=f"app_{app.id}")
        if active_sb:
            sandbox_service.suspend_sandbox(active_sb.id)
    except Exception:
        pass

    return omnigent_dev_service.suspend_dev_session(app)
