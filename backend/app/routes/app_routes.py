"""Application routes for workspace-scoped apps stored in system database 'apps' schema."""

from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.schemas.apps import AppCreate, AppDeployResponse, AppLogsResponse, AppResponse, AppUpdate
from app.services.encryption import encrypt_field
from app.services.app_runner import app_runner_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/apps", tags=["Apps"])


def _to_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "app"


def _to_response(app: App) -> AppResponse:
    return AppResponse(
        id=app.id,
        workspace_id=app.workspace_id,
        workspace_slug=app.workspace_slug,
        name=app.name,
        slug=app.slug,
        description=app.description,
        app_type=app.app_type,
        status=app.status,
        route=app.route,
        git_provider=app.git_provider or "github",
        git_repo_url=app.git_repo_url,
        git_ref=app.git_ref or "main",
        git_ref_type=app.git_ref_type or "branch",
        git_branch=app.git_branch or app.git_ref or "main",
        git_subdir=app.git_subdir,
        entrypoint=app.entrypoint,
        git_credential_type=app.git_credential_type or "none",
        git_credential_nickname=app.git_credential_nickname,
        git_connection_id=app.git_connection_id,
        pat_configured=bool(app.git_pat_enc),
        workspace_identity=app.workspace_identity,
        config=app.config,
        created_by_user_id=app.created_by_user_id,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


@router.get("", response_model=List[AppResponse])
def list_apps(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all applications belonging to the caller's workspace."""
    target_ws = workspace_id or guard.workspace_id
    query = db.query(App)

    if target_ws:
        query = query.filter(App.workspace_id == target_ws)
    elif workspace_slug:
        query = query.filter(App.workspace_slug == workspace_slug)

    apps = query.order_by(App.created_at.desc()).all()
    return [_to_response(a) for a in apps]


@router.post("", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
def create_app(
    body: AppCreate,
    request: Request,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create and register a new workspace-scoped application in the system DB."""
    workspace_id = guard.workspace_id or "default"
    ctx = getattr(request.state, "workspace", None)
    workspace_slug = getattr(ctx, "workspace_slug", None) if ctx else None
    slug = body.slug or _to_slug(body.name)
    route = body.route or f"/{slug}"
    if not route.startswith("/"):
        route = f"/{route}"

    # Generate dedicated App Workspace Identity
    identity_id = f"id_app_{uuid.uuid4().hex[:12]}"
    workspace_identity = {
        "identity_id": identity_id,
        "principal_type": "app_workload",
        "workspace_id": workspace_id,
        "role": "app_executor",
        "scopes": [
            "catalog:read",
            "compute:run",
            "models:inference",
            "agents:invoke",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Encrypt Git PAT if supplied
    git_pat_enc = encrypt_field(body.git_pat) if body.git_pat else None
    git_ref = body.git_ref or body.git_branch or "main"

    app_id = f"app_{uuid.uuid4().hex[:16]}"
    app = App(
        id=app_id,
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        name=body.name,
        slug=slug,
        description=body.description,
        app_type=body.app_type,
        status="active",
        route=route,
        git_provider=body.git_provider or "github",
        git_repo_url=body.git_repo_url,
        git_ref=git_ref,
        git_ref_type=body.git_ref_type or "branch",
        git_branch=git_ref,
        git_subdir=body.git_subdir,
        entrypoint=body.entrypoint,
        git_credential_type=body.git_credential_type or ("pat" if body.git_pat else "none"),
        git_credential_nickname=body.git_credential_nickname,
        git_connection_id=body.git_connection_id,
        git_pat_enc=git_pat_enc,
        workspace_identity=workspace_identity,
        config=body.config or {},
        created_by_user_id=str(guard.principal.id) if guard.principal else None,
    )

    db.add(app)
    db.commit()
    db.refresh(app)
    logger.info("Created app '%s' (id=%s) for workspace '%s'", app.name, app.id, workspace_id)
    return _to_response(app)


@router.get("/{app_id}", response_model=AppResponse)
def get_app(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve an application by ID."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=404, detail="App not found in this workspace.")

    return _to_response(app)


@router.put("/{app_id}", response_model=AppResponse)
def update_app(
    app_id: str,
    body: AppUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update an application."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify app from another workspace.")

    if body.name is not None:
        app.name = body.name
    if body.description is not None:
        app.description = body.description
    if body.app_type is not None:
        app.app_type = body.app_type
    if body.status is not None:
        app.status = body.status
    if body.route is not None:
        app.route = body.route
    if body.git_provider is not None:
        app.git_provider = body.git_provider
    if body.git_repo_url is not None:
        app.git_repo_url = body.git_repo_url
    if body.git_ref is not None:
        app.git_ref = body.git_ref
        app.git_branch = body.git_ref
    if body.git_ref_type is not None:
        app.git_ref_type = body.git_ref_type
    if body.git_subdir is not None:
        app.git_subdir = body.git_subdir
    if body.entrypoint is not None:
        app.entrypoint = body.entrypoint
    if body.git_credential_type is not None:
        app.git_credential_type = body.git_credential_type
    if body.git_credential_nickname is not None:
        app.git_credential_nickname = body.git_credential_nickname
    if body.git_connection_id is not None:
        app.git_connection_id = body.git_connection_id
    if body.git_pat is not None:
        app.git_pat_enc = encrypt_field(body.git_pat) if body.git_pat else None
    if body.config is not None:
        app.config = body.config

    db.commit()
    db.refresh(app)
    return _to_response(app)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete an application and cleanup its running container / runtime storage."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot delete app from another workspace.")

    try:
        app_runner_service.delete_app_runtime(app)
    except Exception as e:
        logger.warning("Error cleaning up app runtime for %s: %s", app.id, e)

    db.delete(app)
    db.commit()
    logger.info("Deleted app '%s' (id=%s)", app.name, app.id)
    return None


@router.post("/{app_id}/deploy", response_model=AppDeployResponse)
def deploy_app(
    app_id: str,
    background_tasks: BackgroundTasks,
    runner_mode: Optional[str] = Query(None, description="Execution target mode: docker | local"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Trigger a new build and deployment for an application into container or local runner."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot deploy app from another workspace.")

    deployment_id = f"dep_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    start_time = datetime.now(timezone.utc)

    # Fetch real latest Git commit info
    git_info = app_runner_service.get_latest_git_commit(app)
    commit_sha = git_info.get("sha") or "latest"
    commit_msg = git_info.get("message")

    try:
        runner_res = app_runner_service.deploy_app(app, runner_mode=runner_mode)
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
        "git_ref": app.git_ref or app.git_branch or "main",
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
    app.status = "active" if deploy_status in ("success", "in_progress") else "error"
    db.commit()
    db.refresh(app)

    if deploy_status == "failed":
        raise HTTPException(status_code=500, detail=f"Deployment failed: {runtime_info.get('error')}")

    # Dispatch background worker to capture and isolate container build logs
    if runtime_info.get("mode") == "kubernetes":
        background_tasks.add_task(app_runner_service.capture_deployment_build_logs, app.id, deployment_id)

    return AppDeployResponse(**deployment_record)


@router.get("/{app_id}/deployments", response_model=List[AppDeployResponse])
def get_app_deployments(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve historical deployment records for an application."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app from another workspace.")

    cfg = dict(app.config or {})
    deployments = cfg.get("deployments", [])
    return [AppDeployResponse(**d) for d in deployments]


@router.get("/{app_id}/deployments/{deployment_id}", response_model=AppDeployResponse)
def get_app_deployment(
    app_id: str,
    deployment_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve a specific deployment record by deployment ID."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app from another workspace.")

    cfg = dict(app.config or {})
    deployments = cfg.get("deployments", [])
    for dep in deployments:
        if dep.get("deployment_id") == deployment_id:
            return AppDeployResponse(**dep)

    raise HTTPException(status_code=404, detail=f"Deployment '{deployment_id}' not found.")


@router.get("/{app_id}/logs", response_model=AppLogsResponse)
def get_app_logs(
    app_id: str,
    tail: int = Query(250, description="Number of tail lines to retrieve"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve actual live runtime container / process logs for an application."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    live_logs = app_runner_service.get_live_logs(app, tail=tail)

    return AppLogsResponse(
        app_id=app.id,
        status=app.status,
        logs=live_logs,
    )


@router.post("/{app_id}/status", response_model=AppResponse)
def update_app_status(
    app_id: str,
    status_value: str = Query(..., alias="status"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Change status of application (active, stopped, maintenance)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify app from another workspace.")

    if status_value.lower() in ("stopped", "inactive"):
        app_runner_service.stop_app(app)
        app.status = "stopped"
    elif status_value.lower() == "active":
        app_runner_service.start_app(app)
        app.status = "active"
    else:
        app.status = status_value

    db.commit()
    db.refresh(app)
    return _to_response(app)


@router.api_route("/{app_id}/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_app_traffic(
    app_id: str,
    path: str,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """Proxy HTTP traffic to the active app container or process."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    return await app_runner_service.proxy_request(app, path, request)
