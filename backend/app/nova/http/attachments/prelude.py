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
