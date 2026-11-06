def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def write_workspace_file(
    app_id: str,
    body: FileWriteRequest,
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save manual code edits to a workspace file (triggering hot reload)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    try:
        unified_reaper_service.touch_app_activity(app.id)
        target_ws = body.workspace_id or workspace_id
        return get_workspace_file_service().write_workspace_file(app, body.path, body.content, workspace_id=target_ws)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
