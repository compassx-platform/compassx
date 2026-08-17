"""File routes — proxied GET/PUT/DELETE file operations on branch pod.

File operations are routed through the pod's own file-service API,
not kubectl exec. See file_service.py for the proxy implementation.
"""

import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.apps.schemas.apps import FileTree, FileContent, FileWrite
from app.apps import services as app_services
from app.apps.services import file_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apps", tags=["apps-files"])

DbDep = Annotated[Session, Depends(get_system_db)]


@router.get("/{app_id}/branches/{branch_id}/files", response_model=FileTree)
async def list_files(app_id: uuid.UUID, branch_id: uuid.UUID, db: DbDep):
    """List all files on the branch pod with status markers (modified/untracked/deleted)."""
    try:
        return await file_service.list_files(db=db, app_id=app_id, branch_id=branch_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{app_id}/branches/{branch_id}/files/{file_path:path}", response_model=FileContent)
async def read_file(
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    file_path: str,
    db: DbDep,
):
    """Read a file's content from the branch pod."""
    try:
        content = await file_service.read_file(
            db=db, app_id=app_id, branch_id=branch_id, path=file_path
        )
        return FileContent(path=file_path, content=content)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.put("/{app_id}/branches/{branch_id}/files/{file_path:path}", status_code=204)
async def write_file(
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    file_path: str,
    payload: FileWrite,
    db: DbDep,
):
    """Write (autosave) a file to the branch pod.

    This triggers hot-reload on the pod but does NOT create a checkpoint.
    """
    try:
        await file_service.write_file(
            db=db, app_id=app_id, branch_id=branch_id, path=file_path, content=payload.content
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.delete("/{app_id}/branches/{branch_id}/files/{file_path:path}", status_code=204)
async def delete_file(
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
    file_path: str,
    db: DbDep,
):
    """Delete a file on the branch pod."""
    try:
        await file_service.delete_file(
            db=db, app_id=app_id, branch_id=branch_id, path=file_path
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
