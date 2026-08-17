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

router = APIRouter(tags=["Nova Attachments"])


class PromoteAttachmentRequest(BaseModel):
    target_catalog_path: str = Field(..., min_length=1)


def _get_session_or_404(db: Session, session_id: int) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


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
    _get_session_or_404(db, session_id)
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"

    records = []
    for upload in files:
        content = await upload.read()
        filename = upload.filename or "file"
        mime_type = upload.content_type or "application/octet-stream"

        rec = upload_attachment(
            session_id=session_id,
            user_id=user_id,
            file_bytes=content,
            filename=filename,
            mime_type=mime_type,
            db=db,
        )

        preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == rec.file_id).first()
        records.append({
            "file_id": str(rec.file_id),
            "session_id": rec.session_id,
            "filename": rec.filename,
            "mime_type": rec.mime_type,
            "size_bytes": rec.size_bytes,
            "status": rec.status,
            "delivery_mode": rec.delivery_mode,
            "extracted_token_count": rec.extracted_token_count,
            "preview_text": preview_rec.preview_text if preview_rec else None,
            "extraction_error": rec.extraction_error,
            "promoted_object_id": str(rec.promoted_object_id) if rec.promoted_object_id else None,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        })

    return {"attachments": records}


@router.get("/api/v1/nova/sessions/{session_id}/attachments")
def list_session_attachments(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
):
    """List all attachments uploaded in this session for rendering chips."""
    _get_session_or_404(db, session_id)
    attachments = (
        db.query(NovaAttachment)
        .filter(NovaAttachment.session_id == session_id, NovaAttachment.status != "purged")
        .order_by(NovaAttachment.created_at.asc())
        .all()
    )

    results = []
    for att in attachments:
        preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == att.file_id).first()
        results.append({
            "file_id": str(att.file_id),
            "session_id": att.session_id,
            "filename": att.filename,
            "mime_type": att.mime_type,
            "size_bytes": att.size_bytes,
            "status": att.status,
            "delivery_mode": att.delivery_mode,
            "extracted_token_count": att.extracted_token_count,
            "preview_text": preview_rec.preview_text if preview_rec else None,
            "extraction_error": att.extraction_error,
            "promoted_object_id": str(att.promoted_object_id) if att.promoted_object_id else None,
            "created_at": att.created_at.isoformat() if att.created_at else None,
        })
    return results


@router.get("/api/v1/nova/sessions/{session_id}/attachments/{file_id}")
def get_session_attachment(
    request: Request,
    session_id: int,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get single attachment status and payload."""
    _get_session_or_404(db, session_id)
    attachment = (
        db.query(NovaAttachment)
        .filter(NovaAttachment.session_id == session_id, NovaAttachment.file_id == file_id)
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == file_id).first()
    context_payload = get_context_payload(file_id, db)

    return {
        "file_id": str(attachment.file_id),
        "session_id": attachment.session_id,
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "status": attachment.status,
        "delivery_mode": attachment.delivery_mode,
        "extracted_token_count": attachment.extracted_token_count,
        "preview_text": preview_rec.preview_text if preview_rec else None,
        "context_payload": context_payload,
        "extraction_error": attachment.extraction_error,
        "promoted_object_id": str(attachment.promoted_object_id) if attachment.promoted_object_id else None,
        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
    }


@router.post("/api/v1/nova/attachments/{file_id}/promote")
def promote_session_attachment(
    request: Request,
    file_id: uuid.UUID,
    body: PromoteAttachmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Promote session file attachment to catalog object."""
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"
    return promote_attachment(file_id, body.target_catalog_path, user_id, db)


@router.delete("/api/v1/nova/sessions/{session_id}/attachments/{file_id}", status_code=204)
def delete_session_attachment(
    request: Request,
    session_id: int,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Remove user attachment from session."""
    _get_session_or_404(db, session_id)
    attachment = (
        db.query(NovaAttachment)
        .filter(NovaAttachment.session_id == session_id, NovaAttachment.file_id == file_id)
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    attachment.status = "purged"
    db.commit()
