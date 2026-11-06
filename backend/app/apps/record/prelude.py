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

logger = logging.getLogger("app.routes.app_routes")



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












_GIT_REF = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")




def _reconcile_app_deployments(app: App, db: Session) -> list:
    """Check and reconcile any stuck 'in_progress' deployments by inspecting logs and status."""
    cfg = dict(app.config or {})
    deployments = list(cfg.get("deployments", []))
    modified = False

    for dep in deployments:
        if dep.get("status") in ("in_progress", "building", "starting", "queued"):
            dep_logs = list(dep.get("logs") or [])
            has_err = any(
                ("[ERROR]" in l or "npm error" in l.lower() or "fatal:" in l.lower() or "build failed" in l.lower())
                for l in dep_logs
            )
            has_ok = any(
                ("[RUNTIME]" in l or "Build phase completed successfully" in l or "Launching application server" in l or "Deployment, Service, and Ingress" in l)
                for l in dep_logs
            )

            if has_err:
                dep["status"] = "failed"
                modified = True
            elif has_ok or app.status == "active":
                dep["status"] = "success"
                # Calculate real duration if available
                try:
                    created_dt = datetime.fromisoformat(dep.get("created_at", "").replace("Z", "+00:00"))
                    dur = round((datetime.now(timezone.utc) - created_dt).total_seconds(), 2)
                    if dur > 0 and dep.get("duration_seconds", 0) <= 2.0:
                        dep["duration_seconds"] = min(dur, 60.0)
                except Exception:
                    pass
                modified = True

    if modified:
        cfg["deployments"] = deployments
        app.config = cfg
        flag_modified(app, "config")
        try:
            db.commit()
            db.refresh(app)
        except Exception as e:
            logger.debug("Failed to commit reconciled deployment status for app %s: %s", app.id, e)

    return deployments
















