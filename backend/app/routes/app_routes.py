"""Application routes for workspace-scoped apps stored in system database 'apps' schema."""

from __future__ import annotations
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.schemas.apps import (
    AppCreate,
    AppDeployResponse,
    AppLogsResponse,
    AppResponse,
    AppRuntimeStatusResponse,
    AppUpdate,
)
from app.services.encryption import encrypt_field
from app.services.app_runner import app_runner_service
from app.services.sandbox_reaper_service import unified_reaper_service

import app.apps.record.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.apps.record.application.list_apps import list_apps as list_apps_action
from app.apps.record.application.create_app import create_app as create_app_action
from app.apps.record.application.get_app import get_app as get_app_action
from app.apps.record.application.update_app import update_app as update_app_action
from app.apps.record.application.delete_app import delete_app as delete_app_action
from app.apps.record.application.deploy_app import deploy_app as deploy_app_action
from app.apps.record.application.get_app_deployments import get_app_deployments as get_app_deployments_action
from app.apps.record.application.get_app_deployment import get_app_deployment as get_app_deployment_action
from app.apps.record.application.get_app_logs import get_app_logs as get_app_logs_action
from app.apps.record.application.get_app_runtime_status import get_app_runtime_status as get_app_runtime_status_action
from app.apps.record.application.start_app_instance import start_app_instance as start_app_instance_action
from app.apps.record.application.stop_app_instance import stop_app_instance as stop_app_instance_action
from app.apps.record.application.update_app_status import update_app_status as update_app_status_action
from app.apps.record.application.proxy_app_traffic import proxy_app_traffic as proxy_app_traffic_action

router = APIRouter(prefix="/api/v1/apps", tags=["Apps"])

@router.get("", response_model=List[AppResponse])
def list_apps(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all applications belonging to the caller's workspace."""
    return list_apps_action(request=request, workspace_id=workspace_id, workspace_slug=workspace_slug, db=db, guard=guard)

@router.post("", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
def create_app(
    body: AppCreate,
    request: Request,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create and register a new workspace-scoped application in the system DB."""
    return create_app_action(body=body, request=request, db=db, guard=guard)

@router.get("/{app_id}", response_model=AppResponse)
def get_app(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve an application by ID."""
    return get_app_action(app_id=app_id, db=db, guard=guard)

@router.put("/{app_id}", response_model=AppResponse)
def update_app(
    app_id: str,
    body: AppUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update an application."""
    return update_app_action(app_id=app_id, body=body, db=db, guard=guard)

@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete an application and cleanup its running container / runtime storage."""
    return delete_app_action(app_id=app_id, db=db, guard=guard)

@router.post("/{app_id}/deploy", response_model=AppDeployResponse)
def deploy_app(
    app_id: str,
    background_tasks: BackgroundTasks,
    runner_mode: Optional[str] = Query(None, description="Execution target mode: docker | local"),
    git_ref: Optional[str] = Query(None, description="Branch or tag to build. Defaults to the app git ref."),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Trigger a new build and deployment for an application into container or local runner."""
    return deploy_app_action(app_id=app_id, background_tasks=background_tasks, runner_mode=runner_mode, git_ref=git_ref, db=db, guard=guard)

@router.get("/{app_id}/deployments", response_model=List[AppDeployResponse])
def get_app_deployments(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve historical deployment records for an application."""
    return get_app_deployments_action(app_id=app_id, db=db, guard=guard)

@router.get("/{app_id}/deployments/{deployment_id}", response_model=AppDeployResponse)
def get_app_deployment(
    app_id: str,
    deployment_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve a specific deployment record by deployment ID."""
    return get_app_deployment_action(app_id=app_id, deployment_id=deployment_id, db=db, guard=guard)

@router.get("/{app_id}/logs", response_model=AppLogsResponse)
def get_app_logs(
    app_id: str,
    tail: int = Query(250, description="Number of tail lines to retrieve"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve actual live runtime container / process logs for an application."""
    return get_app_logs_action(app_id=app_id, tail=tail, db=db, guard=guard)

@router.get("/{app_id}/runtime-status", response_model=AppRuntimeStatusResponse)
def get_app_runtime_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Inspect actual real-time container or Kubernetes pod status for an application."""
    return get_app_runtime_status_action(app_id=app_id, db=db, guard=guard)

@router.post("/{app_id}/start", response_model=AppRuntimeStatusResponse)
def start_app_instance(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start or scale up application container/pod."""
    return start_app_instance_action(app_id=app_id, db=db, guard=guard)

@router.post("/{app_id}/stop", response_model=AppRuntimeStatusResponse)
def stop_app_instance(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop application container/pod."""
    return stop_app_instance_action(app_id=app_id, db=db, guard=guard)

@router.post("/{app_id}/status", response_model=AppResponse)
def update_app_status(
    app_id: str,
    status_value: str = Query(..., alias="status"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Change status of application (active, stopped, starting, stopping)."""
    return update_app_status_action(app_id=app_id, status_value=status_value, db=db, guard=guard)

@router.api_route("/{app_id}/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_app_traffic(
    app_id: str,
    path: str,
    request: Request,
    db: Session = Depends(get_system_db),
):
    """Proxy HTTP traffic to the active app container or process."""
    return await proxy_app_traffic_action(app_id=app_id, path=path, request=request, db=db)

