"""Lifecycle & Inactivity Auto-Shutdown Management Routes.

Provides REST endpoints for querying, configuring, and updating idle auto-shutdown
policies and touching activity across Dev Sandboxes, Deployed Apps, and Compute Runtimes.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.models.app import App
from app.models.dev_workspace import DevWorkspace
from app.models.compute_resources import ComputeResource
from app.services.sandbox_reaper_service import (
    unified_reaper_service,
    DEFAULT_DEV_IDLE_SUSPEND_SECONDS,
    DEFAULT_APP_IDLE_SUSPEND_SECONDS,
    DEFAULT_COMPUTE_IDLE_SUSPEND_SECONDS,
    DEFAULT_STALE_REAP_DAYS,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Lifecycle & Auto-Shutdown"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class DevSandboxLifecycleConfig(BaseModel):
    auto_suspend_enabled: Optional[bool] = None
    idle_timeout_minutes: Optional[int] = None
    auto_reap_enabled: Optional[bool] = None
    stale_reap_days: Optional[int] = None


class AppRuntimeLifecycleConfig(BaseModel):
    auto_suspend_enabled: Optional[bool] = None
    idle_timeout_minutes: Optional[int] = None


class AppLifecycleUpdateRequest(BaseModel):
    dev_sandbox: Optional[DevSandboxLifecycleConfig] = None
    app_runtime: Optional[AppRuntimeLifecycleConfig] = None


class ComputeLifecycleUpdateRequest(BaseModel):
    auto_suspend_enabled: Optional[bool] = None
    idle_timeout_minutes: Optional[int] = None


class ActivityTouchRequest(BaseModel):
    target: Optional[str] = "all"  # "dev_sandbox" | "app_runtime" | "all"


# ── App Lifecycle Endpoints ───────────────────────────────────────────────────

@router.get("/api/v1/apps/{app_id}/lifecycle")
def get_app_lifecycle(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve auto-shutdown and lifecycle settings for both Dev Sandbox and Deployed App runtime."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app from another workspace.")

    cfg = app.config or {}
    dev_cfg = cfg.get("dev_sandbox") or cfg.get("lifecycle", {}).get("dev_sandbox", {})
    runtime_cfg = cfg.get("app_runtime") or cfg.get("lifecycle", {}).get("app_runtime", {})

    # Query active dev workspace for real-time status & last activity
    ws = (
        db.query(DevWorkspace)
        .filter(DevWorkspace.app_id == app_id)
        .order_by(DevWorkspace.last_active_at.desc().nullslast())
        .first()
    )

    dev_last_active = ws.last_active_at.isoformat() if ws and ws.last_active_at else None
    dev_status = ws.status if ws else "inactive"

    app_last_accessed = (
        runtime_cfg.get("last_accessed_at")
        or cfg.get("last_accessed_at")
        or cfg.get("lifecycle", {}).get("last_accessed_at")
        or (app.updated_at.isoformat() if app.updated_at else None)
    )

    return {
        "app_id": app.id,
        "app_name": app.name,
        "dev_sandbox": {
            "auto_suspend_enabled": dev_cfg.get("auto_suspend_enabled", True),
            "idle_timeout_minutes": dev_cfg.get("idle_timeout_minutes", DEFAULT_DEV_IDLE_SUSPEND_SECONDS // 60),
            "auto_reap_enabled": dev_cfg.get("auto_reap_enabled", True),
            "stale_reap_days": dev_cfg.get("stale_reap_days", DEFAULT_STALE_REAP_DAYS),
            "status": dev_status,
            "last_active_at": dev_last_active,
        },
        "app_runtime": {
            "auto_suspend_enabled": runtime_cfg.get("auto_suspend_enabled", False),
            "idle_timeout_minutes": runtime_cfg.get("idle_timeout_minutes", DEFAULT_APP_IDLE_SUSPEND_SECONDS // 60),
            "status": app.status,
            "last_accessed_at": app_last_accessed,
        },
    }


@router.put("/api/v1/apps/{app_id}/lifecycle")
def update_app_lifecycle(
    app_id: str,
    body: AppLifecycleUpdateRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update auto-shutdown and lifecycle settings for Dev Sandbox and/or Deployed App runtime."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify app from another workspace.")

    cfg = dict(app.config or {})
    if "lifecycle" not in cfg or not isinstance(cfg["lifecycle"], dict):
        cfg["lifecycle"] = {}
    if "dev_sandbox" not in cfg or not isinstance(cfg["dev_sandbox"], dict):
        cfg["dev_sandbox"] = {}
    if "app_runtime" not in cfg or not isinstance(cfg["app_runtime"], dict):
        cfg["app_runtime"] = {}

    # Update dev sandbox configuration
    if body.dev_sandbox is not None:
        if body.dev_sandbox.auto_suspend_enabled is not None:
            cfg["dev_sandbox"]["auto_suspend_enabled"] = body.dev_sandbox.auto_suspend_enabled
            cfg["lifecycle"].setdefault("dev_sandbox", {})["auto_suspend_enabled"] = body.dev_sandbox.auto_suspend_enabled
        if body.dev_sandbox.idle_timeout_minutes is not None:
            mins = max(5, int(body.dev_sandbox.idle_timeout_minutes))
            cfg["dev_sandbox"]["idle_timeout_minutes"] = mins
            cfg["lifecycle"].setdefault("dev_sandbox", {})["idle_timeout_minutes"] = mins
        if body.dev_sandbox.auto_reap_enabled is not None:
            cfg["dev_sandbox"]["auto_reap_enabled"] = body.dev_sandbox.auto_reap_enabled
            cfg["lifecycle"].setdefault("dev_sandbox", {})["auto_reap_enabled"] = body.dev_sandbox.auto_reap_enabled
        if body.dev_sandbox.stale_reap_days is not None:
            days = max(1, int(body.dev_sandbox.stale_reap_days))
            cfg["dev_sandbox"]["stale_reap_days"] = days
            cfg["lifecycle"].setdefault("dev_sandbox", {})["stale_reap_days"] = days

    # Update app runtime configuration
    if body.app_runtime is not None:
        if body.app_runtime.auto_suspend_enabled is not None:
            cfg["app_runtime"]["auto_suspend_enabled"] = body.app_runtime.auto_suspend_enabled
            cfg["lifecycle"].setdefault("app_runtime", {})["auto_suspend_enabled"] = body.app_runtime.auto_suspend_enabled
        if body.app_runtime.idle_timeout_minutes is not None:
            mins = max(5, int(body.app_runtime.idle_timeout_minutes))
            cfg["app_runtime"]["idle_timeout_minutes"] = mins
            cfg["lifecycle"].setdefault("app_runtime", {})["idle_timeout_minutes"] = mins

    app.config = cfg
    flag_modified(app, "config")
    db.commit()
    db.refresh(app)

    logger.info("Updated lifecycle config for app '%s' (%s)", app.name, app.id)
    return get_app_lifecycle(app_id, db=db, guard=guard)


@router.post("/api/v1/apps/{app_id}/activity")
def touch_app_activity_endpoint(
    app_id: str,
    body: Optional[ActivityTouchRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Explicitly reset the idle inactivity timer for an app or its dev sandbox."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app from another workspace.")

    target = (body.target if body else "all") or "all"

    if target in ("dev_sandbox", "all"):
        unified_reaper_service.touch_dev_sandbox_activity(app_id)
    if target in ("app_runtime", "all"):
        unified_reaper_service.touch_app_activity(app_id)

    return {
        "status": "touched",
        "app_id": app_id,
        "target": target,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Compute Runtime Lifecycle Endpoints ───────────────────────────────────────

@router.get("/api/v1/compute/resources/{resource_id}/lifecycle")
def get_compute_lifecycle(
    resource_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve auto-shutdown and lifecycle settings for a compute runtime resource."""
    res = db.query(ComputeResource).filter(ComputeResource.id == resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail=f"Compute resource '{resource_id}' not found.")

    if guard.workspace_id and res.workspace_id and res.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access compute resource from another workspace.")

    extra_env = {}
    if res.extra_env:
        try:
            extra_env = json.loads(res.extra_env)
        except Exception:
            extra_env = {}

    lifecycle_cfg = extra_env.get("lifecycle", {})
    auto_suspend_enabled = lifecycle_cfg.get("auto_suspend_enabled", extra_env.get("auto_suspend_enabled", True))
    idle_timeout_minutes = lifecycle_cfg.get(
        "idle_timeout_minutes",
        extra_env.get("idle_timeout_minutes", DEFAULT_COMPUTE_IDLE_SUSPEND_SECONDS // 60),
    )
    last_active_at = (
        lifecycle_cfg.get("last_active_at")
        or extra_env.get("last_active_at")
        or (res.created_at.isoformat() if res.created_at else None)
    )

    return {
        "resource_id": res.id,
        "resource_name": res.name,
        "runtime": res.runtime,
        "desired_status": res.desired_status,
        "auto_suspend_enabled": auto_suspend_enabled,
        "idle_timeout_minutes": idle_timeout_minutes,
        "last_active_at": last_active_at,
    }


@router.put("/api/v1/compute/resources/{resource_id}/lifecycle")
def update_compute_lifecycle(
    resource_id: str,
    body: ComputeLifecycleUpdateRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update auto-shutdown settings for a compute runtime resource."""
    res = db.query(ComputeResource).filter(ComputeResource.id == resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail=f"Compute resource '{resource_id}' not found.")

    if guard.workspace_id and res.workspace_id and res.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify compute resource from another workspace.")

    extra_env = {}
    if res.extra_env:
        try:
            extra_env = json.loads(res.extra_env)
        except Exception:
            extra_env = {}

    if "lifecycle" not in extra_env or not isinstance(extra_env["lifecycle"], dict):
        extra_env["lifecycle"] = {}

    if body.auto_suspend_enabled is not None:
        extra_env["lifecycle"]["auto_suspend_enabled"] = body.auto_suspend_enabled
        extra_env["auto_suspend_enabled"] = body.auto_suspend_enabled

    if body.idle_timeout_minutes is not None:
        mins = max(5, int(body.idle_timeout_minutes))
        extra_env["lifecycle"]["idle_timeout_minutes"] = mins
        extra_env["idle_timeout_minutes"] = mins

    res.extra_env = json.dumps(extra_env)
    db.commit()
    db.refresh(res)

    logger.info("Updated lifecycle config for compute resource '%s' (%s)", res.name, res.id)
    return get_compute_lifecycle(resource_id, db=db, guard=guard)


@router.post("/api/v1/compute/resources/{resource_id}/activity")
def touch_compute_activity_endpoint(
    resource_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Explicitly reset the idle inactivity timer for a compute runtime resource."""
    res = db.query(ComputeResource).filter(ComputeResource.id == resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail=f"Compute resource '{resource_id}' not found.")

    if guard.workspace_id and res.workspace_id and res.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access compute resource from another workspace.")

    unified_reaper_service.touch_compute_activity(resource_id)

    return {
        "status": "touched",
        "resource_id": resource_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
