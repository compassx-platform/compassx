def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def diff_workspace_file(
    app_id: str,
    path: str = Query(..., description="Relative file path in workspace"),
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Unified diff of one sandbox file against the last commit."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        return get_workspace_file_service().diff_workspace_file(app, path, workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
