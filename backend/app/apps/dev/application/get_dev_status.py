def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def get_dev_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Check status of active development sandbox and Databricks Omnigent server."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.get_dev_session(app)
