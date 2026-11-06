def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def stop_app_instance(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop application container/pod."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify app from another workspace.")

    app.status = "stopping"
    db.commit()
    db.refresh(app)

    app_runner_service.stop_app(app)
    status_info = app_runner_service.get_runtime_status(app, db=db)
    return AppRuntimeStatusResponse(**status_info)
