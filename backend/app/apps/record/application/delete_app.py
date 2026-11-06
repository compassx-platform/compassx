def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def delete_app(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete an application and cleanup its running container / runtime storage."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot delete app from another workspace.")

    try:
        app_runner_service.delete_app_runtime(app)
    except Exception as e:
        logger.warning("Error cleaning up app runtime for %s: %s", app.id, e)

    db.delete(app)
    db.commit()
    logger.info("Deleted app '%s' (id=%s)", app.name, app.id)
    return None
