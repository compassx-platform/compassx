def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def resume_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Resume a suspended dev sandbox (restore compute to 1 replica)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)

    try:
        sandbox_service.resume_sandbox(f"dev-app-{app.id}")
    except Exception:
        pass

    try:
        active_sb = sandbox_service.find_active_sandbox(consumer_key=f"app_{app.id}")
        if active_sb:
            sandbox_service.resume_sandbox(active_sb.id)
    except Exception:
        pass

    return omnigent_dev_service.resume_dev_session(app)
