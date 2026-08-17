"""Branch routes — create/delete/checkpoint/diff."""

import uuid
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.apps.models.apps import App, AppBranch
from app.apps.schemas.apps import (
    BranchCreate, BranchRead, CheckpointRequest, CheckpointResponse, DiffResult,
)
from app.apps.services.pod_service import PodService
from app.apps.services.credential_service import CredentialService
from app.apps.services.source_control.factory import get_source_control_backend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apps", tags=["apps-branches"])

DbDep = Annotated[Session, Depends(get_system_db)]


@router.get("/{app_id}/branches", response_model=list[BranchRead])
async def list_branches(app_id: uuid.UUID, db: DbDep):
    """List all branches for an app."""
    return db.query(AppBranch).filter(AppBranch.app_id == app_id).all()


@router.post("/{app_id}/branches", response_model=BranchRead, status_code=201)
async def create_branch(app_id: uuid.UUID, payload: BranchCreate, db: DbDep):
    """Create a new branch.

    Enforces the per-(app, user) concurrent branch cap (§5).
    Provisions a branch pod after creating the branch record.
    """
    app: Optional[App] = db.query(App).filter(App.app_id == app_id).one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"App {app_id} not found")

    # TODO: replace with current user from auth context
    user_id = app.owner_id

    pod_svc = PodService(db)
    try:
        pod_svc.check_branch_cap(app_id=app_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    sc = get_source_control_backend(db=db, workspace_id=app.workspace_id)
    branch = await sc.create_branch(
        app_id=app_id,
        name=payload.name,
        from_branch_id=payload.from_branch_id,
        created_by=user_id,
    )
    db.flush()

    # Mint token and provision branch pod
    cred_svc = CredentialService(db)
    scoped_token = await cred_svc.mint_scoped_token(app_id=app_id)

    head_commit_id = branch.head_commit_id
    await pod_svc.provision_branch_pod(
        app_id=app_id,
        branch_id=branch.branch_id,
        commit_id=head_commit_id,
        scoped_token=scoped_token,
        terminal_enabled=True,
    )

    db.commit()
    db.refresh(branch)
    logger.info("Branch created: %s (app=%s)", branch.name, app_id)
    return branch


@router.delete("/{app_id}/branches/{branch_id}", status_code=204)
async def delete_branch(app_id: uuid.UUID, branch_id: uuid.UUID, db: DbDep):
    """Delete a branch and terminate its pod."""
    branch: Optional[AppBranch] = (
        db.query(AppBranch)
        .filter(AppBranch.branch_id == branch_id, AppBranch.app_id == app_id)
        .one_or_none()
    )
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")

    from app.apps.models.apps import AppPod
    pod_svc = PodService(db)
    running_pods = (
        db.query(AppPod)
        .filter(AppPod.branch_id == branch_id, AppPod.status.in_(["starting", "running"]))
        .all()
    )
    for pod in running_pods:
        await pod_svc.terminate_pod(pod.pod_id)

    db.delete(branch)
    db.commit()
    logger.info("Branch deleted: %s (app=%s)", branch_id, app_id)


@router.post("/{app_id}/branches/{branch_id}/checkpoint", response_model=CheckpointResponse)
async def checkpoint_branch(
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    payload: CheckpointRequest,
    db: DbDep,
):
    """Create a versioned checkpoint (commit) of the branch's current working tree.

    This is a human-triggered action — Pi agent does NOT call this automatically (§7).
    """
    branch: Optional[AppBranch] = (
        db.query(AppBranch)
        .filter(AppBranch.branch_id == branch_id, AppBranch.app_id == app_id)
        .one_or_none()
    )
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")

    app: App = db.query(App).filter(App.app_id == app_id).one()
    sc = get_source_control_backend(db=db, workspace_id=app.workspace_id)

    commit = await sc.checkpoint(
        branch_id=branch_id,
        message=payload.message,
        author=str(app.owner_id),  # TODO: replace with auth context user
    )
    db.commit()
    db.refresh(commit)
    logger.info("Checkpoint created: %s on branch %s", commit.commit_id, branch_id)
    return commit


@router.get("/{app_id}/branches/{branch_id}/diff", response_model=DiffResult)
async def diff_branch(
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    against: uuid.UUID = Query(..., description="Commit ID to diff against"),
    detail: bool = Query(False, description="Include line-level diffs"),
    db: DbDep = None,
):
    """Compare branch HEAD against a specific commit."""
    branch: Optional[AppBranch] = (
        db.query(AppBranch)
        .filter(AppBranch.branch_id == branch_id, AppBranch.app_id == app_id)
        .one_or_none()
    )
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")
    if branch.head_commit_id is None:
        raise HTTPException(status_code=400, detail="Branch has no commits yet")

    app: App = db.query(App).filter(App.app_id == app_id).one()
    sc = get_source_control_backend(db=db, workspace_id=app.workspace_id)
    changes = await sc.diff(
        commit_a=against,
        commit_b=branch.head_commit_id,
        include_line_diff=detail,
    )

    from app.apps.schemas.apps import FileDiff as FileDiffSchema
    return DiffResult(
        commit_a=against,
        commit_b=branch.head_commit_id,
        changes=[
            FileDiffSchema(path=c.path, status=c.status, diff_lines=c.diff_lines)
            for c in changes
        ],
    )
