def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def verify_git_workspace(
    app_id: str,
    body: Optional[VerifyGitRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Verify git status, branch, and working tree for dev workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    workspace_id = body.workspace_id if body else None
    workspace_name = body.workspace_name if body else None

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.verify_git_workspace(
        app, workspace_id=workspace_id, workspace_name=workspace_name
    )
