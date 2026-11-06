def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def publish_dev_changes(
    app_id: str,
    body: Optional[PublishRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Commit workspace changes and push to its dedicated remote Git branch."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    user_id = str(guard.principal.id) if guard.principal else "system"
    commit_msg = body.commit_message if body else None
    ws_id = body.workspace_id if body else None
    ws_name = body.workspace_name if body else None
    try:
        unified_reaper_service.touch_app_activity(app.id)
        res = omnigent_dev_service.publish_dev_changes(
            app,
            commit_message=commit_msg,
            user_id=user_id,
            workspace_id=ws_id,
            workspace_name=ws_name,
        )
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to publish dev changes for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=str(e) or "Failed to publish sandbox changes.") from e
