def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def stop_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop the development sandbox container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    db.expunge(app)
    db.close()

    # 1. Terminate sandbox instance in centralized sandbox_service
    try:
        sandbox_service.terminate_sandbox(f"dev-app-{app.id}")
    except Exception as sb_err:
        logger.debug("Sandbox terminate error for dev-app-%s: %s", app.id, sb_err)

    try:
        active_sb = sandbox_service.find_active_sandbox(consumer_key=f"app_{app.id}")
        if active_sb:
            sandbox_service.terminate_sandbox(active_sb.id)
    except Exception as sb_err2:
        logger.debug("Sandbox terminate error for consumer app_%s: %s", app.id, sb_err2)

    # 2. Stop legacy dev session
    return omnigent_dev_service.stop_dev_session(app)
