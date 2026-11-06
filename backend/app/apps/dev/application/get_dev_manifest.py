def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def get_dev_manifest(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve and parse the app.yaml manifest or generated runtime configuration for an app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    repo_dir = omnigent_dev_service.get_repo_dir(app)
    manifest = app_manifest_service.load_manifest(repo_dir)
    if not manifest:
        try:
            from app.services.drivers.factory import driver_factory
            dev_driver = driver_factory.get_dev_driver()
            clean_id = app.id.replace("_", "-").lower()
            manifest = omnigent_dev_service._resolve_app_manifest(app, dev_driver, f"{clean_id}/default", repo_dir, repo_dir)
        except Exception:
            pass
    run_cfg = app_manifest_service.get_run_config(manifest)
    return {
        "app_id": app.id,
        "has_manifest": manifest is not None,
        "manifest": manifest,
        "run_config": run_cfg or {
            "gateway_port": 8080,
            "frontend_port": 4000,
            "backend_port": 8000,
            "frontend_command": "npm run dev",
            "backend_command": "uvicorn main:app --port 8000",
        },
    }
