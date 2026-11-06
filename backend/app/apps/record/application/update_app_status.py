def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def update_app_status(
    app_id: str,
    status_value: str = Query(..., alias="status"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Change status of application (active, stopped, starting, stopping)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify app from another workspace.")

    if status_value.lower() in ("stopped", "inactive"):
        app.status = "stopping"
        db.commit()
        app_runner_service.stop_app(app)
        app_runner_service.get_runtime_status(app, db=db)
    elif status_value.lower() in ("active", "starting", "provisioning"):
        app.status = "starting"
        db.commit()
        app_runner_service.start_app(app)
        app_runner_service.get_runtime_status(app, db=db)
    else:
        app.status = status_value
        db.commit()

    db.refresh(app)
    return _to_response(app)
