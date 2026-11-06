def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def get_workspace_git_commits(
    app_id: str,
    workspace_id: str,
    limit: Optional[int] = Query(50),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve Git commit history for a specific workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)

    return omnigent_dev_service.get_git_commits(
        app=app,
        workspace_id=workspace_id,
        limit=limit or 50,
    )
