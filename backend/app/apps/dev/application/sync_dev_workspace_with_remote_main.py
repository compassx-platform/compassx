def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def sync_dev_workspace_with_remote_main(
    app_id: str,
    workspace_id: str,
    body: Optional[SyncWorkspaceRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch remote main and merge it into this sandbox workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        base_branch = (body.base_branch if body and body.base_branch else "main")
        return omnigent_dev_service.sync_workspace_with_remote_main(
            app, workspace_id=workspace_id, base_branch=base_branch
        )
    except Exception as e:
        logger.exception("Failed to sync dev workspace %s with remote main: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to sync with remote main: {str(e)}")
