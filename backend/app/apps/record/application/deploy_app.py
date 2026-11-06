def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def deploy_app(
    app_id: str,
    background_tasks: BackgroundTasks,
    runner_mode: Optional[str] = Query(None, description="Execution target mode: docker | local"),
    git_ref: Optional[str] = Query(None, description="Branch or tag to build. Defaults to the app git ref."),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Trigger a new build and deployment for an application into container or local runner."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot deploy app from another workspace.")
    if git_ref and not _GIT_REF.match(git_ref):
        raise HTTPException(status_code=400, detail="Invalid git ref.")

    deployment_id = f"dep_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now(timezone.utc)

    # Fetch real latest Git commit info
    git_info = app_runner_service.get_latest_git_commit(app, git_ref=git_ref)
    commit_sha = git_info.get("sha") or "latest"
    commit_msg = git_info.get("message")

    try:
        runner_res = app_runner_service.deploy_app(app, runner_mode=runner_mode, git_ref=git_ref)
        runtime_info = runner_res["runtime_info"]
        logs = runner_res["build_logs"]
        deploy_status = "in_progress" if runtime_info.get("mode") == "kubernetes" else "success"
    except Exception as e:
        logger.exception("App deployment failed for %s: %s", app.name, e)
        logs = [f"[ERROR] Deployment failed: {str(e)}"]
        runtime_info = {"status": "error", "error": str(e)}
        deploy_status = "failed"

    duration = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)

    cfg = dict(app.config or {})
    deployments = list(cfg.get("deployments", []))
    deployment_record = {
        "deployment_id": deployment_id,
        "app_id": app.id,
        "status": deploy_status,
        "commit_sha": commit_sha,
        "commit_message": commit_msg,
        "git_ref": git_ref or app.git_ref or app.git_branch or "main",
        "duration_seconds": duration,
        "triggered_by": str(guard.principal.id) if guard.principal else "system",
        "created_at": now_iso,
        "logs": logs,
    }
    deployments.insert(0, deployment_record)
    cfg["deployments"] = deployments[:20]
    cfg["logs"] = logs
    cfg["runtime"] = runtime_info

    app.config = cfg
    flag_modified(app, "config")
    app.status = "active" if deploy_status in ("success", "in_progress") else "error"
    db.commit()
    db.refresh(app)

    if deploy_status == "failed":
        raise HTTPException(status_code=500, detail=f"Deployment failed: {runtime_info.get('error')}")

    # Dispatch background worker to capture and isolate container build logs
    if runtime_info.get("mode") == "kubernetes":
        background_tasks.add_task(app_runner_service.capture_deployment_build_logs, app.id, deployment_id)

    return AppDeployResponse(**deployment_record)
