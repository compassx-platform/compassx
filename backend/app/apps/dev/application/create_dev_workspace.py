def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def create_dev_workspace(
    app_id: str,
    body: CreateWorkspaceRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new dev workspace folder record for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Workspace name cannot be empty.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        return omnigent_dev_service.create_dev_workspace(
            app,
            name=body.name.strip(),
            git_branch=body.git_branch,
            base_branch=body.base_branch or "main",
            fetch_remote=body.fetch_remote if body.fetch_remote is not None else True,
        )
    except Exception as e:
        logger.exception("Failed to create dev workspace for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to create dev workspace: {str(e)}")
