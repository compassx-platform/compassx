def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def activate_dev_workspace(
    app_id: str,
    workspace_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Instantly switch the active sandbox (git worktree) without restarting container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        return omnigent_dev_service.activate_dev_workspace(app, workspace_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to activate dev workspace %s for app %s: %s", workspace_id, app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to activate dev workspace: {str(e)}")
