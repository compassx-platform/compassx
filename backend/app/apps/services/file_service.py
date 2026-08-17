"""File service — proxied file CRUD to branch pod with local fallback for development.

File operations go through the pod's own file-service HTTP API when available.
If no running pod is found or connection fails, it transparently falls back to
the local filesystem (scratch/workspaces/app_{app_id}_branch_{branch_id}), enabling
full local development without Kubernetes.
"""

import logging
import uuid
import os
import hashlib
import json
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.apps.models.apps import AppBranch, AppPod
from app.apps.schemas.apps import FileMeta, FileTree

logger = logging.getLogger(__name__)

# The pod's file-service listens on this internal port
_FILE_SERVICE_PORT = 7000
_TIMEOUT = 5.0  # Fail fast to fallback locally if pod is unreachable


def _pod_base_url(pod: AppPod) -> str:
    return f"http://{pod.k8s_pod_name}.compassx-apps.svc.cluster.local:{_FILE_SERVICE_PORT}"


def _get_active_branch_pod(db: Session, app_id: uuid.UUID, branch_id: uuid.UUID) -> Optional[AppPod]:
    return (
        db.query(AppPod)
        .filter(
            AppPod.app_id == app_id,
            AppPod.branch_id == branch_id,
            AppPod.pod_kind == "branch",
            AppPod.status == "running",
        )
        .order_by(AppPod.created_at.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Local Filesystem Fallback Helpers
# ---------------------------------------------------------------------------

def _local_workspace_path(app_id: uuid.UUID, branch_id: uuid.UUID) -> str:
    # Get backend directory path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(base_dir, "scratch", "workspaces", f"app_{app_id}_branch_{branch_id}")
    os.makedirs(path, exist_ok=True)
    return path


async def _ensure_local_workspace_initialized(
    db: Session,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    workspace_path: str,
) -> None:
    if os.listdir(workspace_path):
        return  # Already initialized

    branch = db.query(AppBranch).filter(AppBranch.branch_id == branch_id).one_or_none()
    if branch and branch.head_commit_id:
        try:
            from app.apps.services.source_control.factory import get_source_control_backend
            sc = get_source_control_backend(db, workspace_id=branch.app.workspace_id)
            await sc.materialize(branch.head_commit_id, workspace_path)
            logger.info("Materialized head commit %s for local workspace", branch.head_commit_id)
            return
        except Exception as exc:
            logger.error("Failed to materialize head commit for local workspace: %s", exc)

    # Populate default scaffold files if no commit or materialization failed
    from app.apps.services.pod_service import SCAFFOLD_FILES
    for rel_path, content in SCAFFOLD_FILES.items():
        abs_path = os.path.join(workspace_path, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
    logger.info("Initialized local workspace with default scaffold files")


async def _local_list_files(
    db: Session,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    workspace_path: str,
) -> FileTree:
    await _ensure_local_workspace_initialized(db, app_id, branch_id, workspace_path)

    # Scan local directory relative paths under /backend and /frontend
    local_files: dict[str, bytes] = {}
    for root, _, files in os.walk(workspace_path):
        for file in files:
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, workspace_path).replace("\\", "/")
            if rel_path.startswith("backend/") or rel_path.startswith("frontend/"):
                try:
                    with open(abs_path, "rb") as f:
                        local_files[rel_path] = f.read()
                except Exception:
                    pass

    # Read manifest of HEAD commit
    path_hash_map: dict[str, str] = {}
    branch = db.query(AppBranch).filter(AppBranch.branch_id == branch_id).one_or_none()
    if branch and branch.head_commit_id:
        from app.apps.models.apps import AppCommit
        commit = db.query(AppCommit).filter(AppCommit.commit_id == branch.head_commit_id).one_or_none()
        if commit:
            try:
                from app.apps.services.source_control.factory import get_blob_backend
                blob = get_blob_backend(db)
                from app.apps.services.source_control.native_backend import _manifest_path
                manifest_key = _manifest_path(app_id, commit.tree_manifest_hash)
                manifest_data = await blob.read_bytes(manifest_key)
                path_hash_map = json.loads(manifest_data)
            except Exception as exc:
                logger.warning("Could not read HEAD commit manifest for diff: %s", exc)

    files_meta = []
    # Local files status (clean, modified, untracked)
    for rel_path, content in local_files.items():
        size_bytes = len(content)
        if rel_path not in path_hash_map:
            status = "untracked"
        else:
            local_hash = hashlib.sha256(content).hexdigest()
            status = "clean" if local_hash == path_hash_map[rel_path] else "modified"
        files_meta.append(FileMeta(path=rel_path, size_bytes=size_bytes, status=status))

    # Deleted files status
    for rel_path in path_hash_map:
        if rel_path not in local_files:
            files_meta.append(FileMeta(path=rel_path, size_bytes=0, status="deleted"))

    return FileTree(files=files_meta)


# ---------------------------------------------------------------------------
# File CRUD (proxied to pod file-service with local fallback)
# ---------------------------------------------------------------------------

async def list_files(
    db: Session,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> FileTree:
    """List all files on the branch pod with status markers."""
    pod = _get_active_branch_pod(db, app_id, branch_id)
    if pod is not None:
        try:
            url = f"{_pod_base_url(pod)}/files"
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            return FileTree(files=[FileMeta(**f) for f in data.get("files", [])])
        except Exception as exc:
            logger.warning("Failed connecting to branch pod %s: %s. Falling back to local workspace.", pod.k8s_pod_name, exc)

    # Local fallback
    workspace_path = _local_workspace_path(app_id, branch_id)
    return await _local_list_files(db, app_id, branch_id, workspace_path)


async def read_file(
    db: Session,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    path: str,
) -> str:
    """Read a single file's content from the branch pod."""
    pod = _get_active_branch_pod(db, app_id, branch_id)
    if pod is not None:
        try:
            url = f"{_pod_base_url(pod)}/files/{path}"
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json().get("content", "")
        except Exception as exc:
            logger.warning("Failed connecting to branch pod %s: %s. Falling back to local workspace.", pod.k8s_pod_name, exc)

    # Local fallback
    workspace_path = _local_workspace_path(app_id, branch_id)
    await _ensure_local_workspace_initialized(db, app_id, branch_id, workspace_path)
    abs_path = os.path.join(workspace_path, path)
    if not os.path.exists(abs_path):
        raise RuntimeError(f"File not found: {path}")
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


async def write_file(
    db: Session,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    path: str,
    content: str,
) -> None:
    """Write (create or overwrite) a file on the branch pod."""
    pod = _get_active_branch_pod(db, app_id, branch_id)
    if pod is not None:
        try:
            url = f"{_pod_base_url(pod)}/files/{path}"
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.put(url, json={"content": content})
                resp.raise_for_status()
                return
        except Exception as exc:
            logger.warning("Failed connecting to branch pod %s: %s. Falling back to local workspace.", pod.k8s_pod_name, exc)

    # Local fallback
    workspace_path = _local_workspace_path(app_id, branch_id)
    await _ensure_local_workspace_initialized(db, app_id, branch_id, workspace_path)
    abs_path = os.path.join(workspace_path, path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)


async def delete_file(
    db: Session,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    path: str,
) -> None:
    """Delete a file on the branch pod."""
    pod = _get_active_branch_pod(db, app_id, branch_id)
    if pod is not None:
        try:
            url = f"{_pod_base_url(pod)}/files/{path}"
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.delete(url)
                resp.raise_for_status()
                return
        except Exception as exc:
            logger.warning("Failed connecting to branch pod %s: %s. Falling back to local workspace.", pod.k8s_pod_name, exc)

    # Local fallback
    workspace_path = _local_workspace_path(app_id, branch_id)
    await _ensure_local_workspace_initialized(db, app_id, branch_id, workspace_path)
    abs_path = os.path.join(workspace_path, path)
    if os.path.exists(abs_path):
        os.remove(abs_path)


# ---------------------------------------------------------------------------
# Working tree snapshot (used by NativeSourceControlBackend.checkpoint)
# ---------------------------------------------------------------------------

async def get_working_tree_files(branch_id: uuid.UUID) -> dict[str, bytes]:
    """Return all files from the pod working tree as {relative_path: bytes}."""
    from app.database import SystemSessionLocal
    from app.apps.models.apps import AppBranch as _AppBranch, AppPod as _AppPod

    db = SystemSessionLocal()
    try:
        branch = db.query(_AppBranch).filter(_AppBranch.branch_id == branch_id).one()
        pod = (
            db.query(_AppPod)
            .filter(
                _AppPod.branch_id == branch_id,
                _AppPod.pod_kind == "branch",
                _AppPod.status == "running",
            )
            .order_by(_AppPod.created_at.desc())
            .first()
        )

        if pod is not None:
            try:
                url = f"{_pod_base_url(pod)}/snapshot"
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    import base64
                    raw = resp.json()
                    return {p: base64.b64decode(c) for p, c in raw.items()}
            except Exception as exc:
                logger.warning("Failed to download snapshot from pod %s: %s. Falling back to local.", pod.k8s_pod_name, exc)

        # Local fallback
        workspace_path = _local_workspace_path(branch.app_id, branch_id)
        await _ensure_local_workspace_initialized(db, branch.app_id, branch_id, workspace_path)

        local_files = {}
        for root, _, files in os.walk(workspace_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, workspace_path).replace("\\", "/")
                if rel_path.startswith("backend/") or rel_path.startswith("frontend/"):
                    try:
                        with open(abs_path, "rb") as f:
                            local_files[rel_path] = f.read()
                    except Exception:
                        pass
        return local_files
    finally:
        db.close()
