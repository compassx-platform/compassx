"""FastAPI Routes for Nova File Attachments.

Implements section 3 of architecture/agents/file-attachments-spec.md
"""

from __future__ import annotations

import uuid

from typing import List, Optional

from pydantic import BaseModel, Field

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile

from sqlalchemy.orm import Session

from app.database import get_system_db as get_db

from app.dependencies import get_current_user

from app.models.agents import ChatSession, NovaAttachment, NovaAttachmentPreview

from app.nova.services.attachment_service import (
    upload_attachment,
    get_context_payload,
    promote_attachment,
)

class PromoteAttachmentRequest(BaseModel):
    target_catalog_path: str = Field(..., min_length=1)

def _get_session_or_404(db: Session, session_id: int) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

import app.nova.http.attachments.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.nova.http.attachments.application.upload_session_attachments import upload_session_attachments as upload_session_attachments_action
from app.nova.http.attachments.application.list_session_attachments import list_session_attachments as list_session_attachments_action
from app.nova.http.attachments.application.get_session_attachment import get_session_attachment as get_session_attachment_action
from app.nova.http.attachments.application.promote_session_attachment import promote_session_attachment as promote_session_attachment_action
from app.nova.http.attachments.application.delete_session_attachment import delete_session_attachment as delete_session_attachment_action

router = APIRouter(tags=["Nova Attachments"])

@router.post("/api/v1/nova/sessions/{session_id}/attachments", status_code=201)
async def upload_session_attachments(
    request: Request,
    session_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upload one or more session-scoped attachments to Nova."""
    return await upload_session_attachments_action(request=request, session_id=session_id, background_tasks=background_tasks, files=files, db=db, current_user=current_user)

@router.get("/api/v1/nova/sessions/{session_id}/attachments")
def list_session_attachments(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
):
    """List all attachments uploaded in this session for rendering chips."""
    return list_session_attachments_action(request=request, session_id=session_id, db=db)

@router.get("/api/v1/nova/sessions/{session_id}/attachments/{file_id}")
def get_session_attachment(
    request: Request,
    session_id: int,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get single attachment status and payload."""
    return get_session_attachment_action(request=request, session_id=session_id, file_id=file_id, db=db)

@router.post("/api/v1/nova/attachments/{file_id}/promote")
def promote_session_attachment(
    request: Request,
    file_id: uuid.UUID,
    body: PromoteAttachmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Promote session file attachment to catalog object."""
    return promote_session_attachment_action(request=request, file_id=file_id, body=body, db=db, current_user=current_user)

@router.delete("/api/v1/nova/sessions/{session_id}/attachments/{file_id}", status_code=204)
def delete_session_attachment(
    request: Request,
    session_id: int,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Remove user attachment from session."""
    return delete_session_attachment_action(request=request, session_id=session_id, file_id=file_id, db=db)
