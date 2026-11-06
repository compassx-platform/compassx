def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def update_dev_manifest(
    app_id: str,
    body: AppManifestUpdateRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save or generate an app.yaml manifest directly into the app repository."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    repo_dir = omnigent_dev_service.get_repo_dir(app)
    os.makedirs(repo_dir, exist_ok=True)
    manifest_path = os.path.join(repo_dir, "app.yaml")

    if body.raw_yaml and body.raw_yaml.strip():
        yaml_content = body.raw_yaml.strip()
    else:
        manifest_dict: Dict[str, Any] = {
            "version": "1",
            "name": app.slug or app.name or app.id,
            "services": {}
        }
        if body.backend_command:
            manifest_dict["services"]["backend"] = {
                "command": body.backend_command,
                "port": body.backend_port or 8000,
                "dir": body.backend_dir or ".",
                "path": "/api",
            }
        if body.frontend_command:
            manifest_dict["services"]["frontend"] = {
                "command": body.frontend_command,
                "port": body.frontend_port or 4000,
                "dir": body.frontend_dir or "frontend",
                "path": "/",
            }
        if body.install_command:
            manifest_dict["install"] = body.install_command
        if body.env:
            manifest_dict["env"] = body.env

        yaml_content = yaml.dump(manifest_dict, sort_keys=False, default_flow_style=False)

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
    except Exception:
        pass

    # Sync to dev sandbox pod if running
    try:
        from app.services.drivers.factory import driver_factory
        import base64
        dev_driver = driver_factory.get_dev_driver()
        clean_id = app.id.replace("_", "-").lower()
        b64 = base64.b64encode(yaml_content.encode("utf-8")).decode("ascii")
        sync_cmd = f"mkdir -p /workspace && echo '{b64}' | base64 -d | tee /workspace/app.yaml /workspaces/{clean_id}/*/app.yaml 2>/dev/null || true"
        dev_driver.exec_command_in_dev(app, sync_cmd)
    except Exception:
        pass

    parsed = app_manifest_service.parse_manifest_text(yaml_content, manifest_path=manifest_path)
    run_cfg = app_manifest_service.get_run_config(parsed)

    return {
        "app_id": app.id,
        "status": "saved",
        "manifest_path": manifest_path,
        "manifest": parsed,
        "run_config": run_cfg,
    }
