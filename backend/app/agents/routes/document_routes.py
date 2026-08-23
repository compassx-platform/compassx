"""Document Upload API Routes — Part F of AI Data Engineer Spec v5.

Endpoints:
  POST   /agents/{agent_id}/sessions/{session_id}/documents   — upload file(s)
  GET    /agents/{agent_id}/sessions/{session_id}/documents   — list session docs
  DELETE /agents/{agent_id}/sessions/{session_id}/documents/{doc_id} — remove doc

Uploaded files are stored, extracted, embedded (background task), and their
doc_id is linked into the active plan's context.uploaded_documents if one exists.
"""

from __future__ import annotations

import logging
import os
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db
from app.dependencies import get_current_user
from app.models.agents import Agent, ChatSession, RagDocument, DocumentStatus
from app.agents.services.document_processor import parse_document, process_document
from app.agents.services.agent.plan_service import PlanService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/{agent_id}/sessions/{session_id}", tags=["Documents"])

ACCEPTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "text/plain",
    "text/markdown",
    "application/json",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session_or_404(db: Session, agent_id: int, session_id: int) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.agent_id == agent_id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Session not found")
    return session


def _link_doc_to_plan(session_id: int, doc_id: int) -> None:
    """Add doc_id to the active plan's context.uploaded_documents if one exists."""
    try:
        plan_svc = PlanService()
        active_plan = plan_svc.get_active_plan_for_session(session_id)
        if active_plan:
            doc_ref = str(doc_id)
            if doc_ref not in active_plan.context.uploaded_documents:
                active_plan.context.uploaded_documents.append(doc_ref)
                plan_svc.save_plan(active_plan)
                logger.info("Linked doc %s to plan %s", doc_id, active_plan.plan_id)
    except Exception as exc:
        logger.warning("Could not link doc to plan: %s", exc)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/documents", status_code=201)
async def upload_documents(
    request: Request,
    agent_id: int,
    session_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upload one or more documents to the session evidence pool (Part F2)."""
    _get_session_or_404(db, agent_id, session_id)

    # Resolve accepted types from agent manifest
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    accepted_exts: set[str] = {"pdf", "docx", "xlsx", "csv", "txt", "md", "json", "png", "jpg", "jpeg", "webp", "gif", "svg"}
    if agent and agent.manifest:
        from app.agents.schemas.agent_manifest import AgentManifest
        try:
            m = AgentManifest.model_validate(agent.manifest)
            if not m.capabilities.document_upload.enabled:
                raise HTTPException(403, "Document upload is disabled for this agent")
            accepted_exts = set(m.capabilities.document_upload.accepted_types)
        except Exception:
            pass

    results = []
    for upload in files:
        ext = (upload.filename or "").rsplit(".", 1)[-1].lower() if "." in (upload.filename or "") else ""
        if ext not in accepted_exts:
            results.append({"filename": upload.filename, "error": f"File type '{ext}' not accepted", "ok": False})
            continue

        content = await upload.read()
        mime = upload.content_type or "application/octet-stream"

        # Extract full parsed text synchronously — fast (less than 100ms)
        try:
            full_text = parse_document(content, mime, upload.filename or "file")
            preview = full_text[:1000]
        except Exception as exc:
            logger.warning("Synchronous document parse failed for %s: %s", upload.filename, exc)
            full_text = ""
            preview = ""

        doc = RagDocument(
            agent_id=agent_id,
            session_id=session_id,
            filename=upload.filename or "upload",
            mime_type=mime,
            size_bytes=len(content),
            status=DocumentStatus.processing,
            extracted_preview=preview,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Persist full extracted text blob & raw binary file immediately
        try:
            from app.nova.services.attachment_service import STORAGE_BASE_DIR, _ensure_dir
            doc_dir = os.path.join(STORAGE_BASE_DIR, "sessions", str(session_id), "rag_docs", str(doc.id))
            _ensure_dir(os.path.join(doc_dir, "keep"))

            # Save full parsed text
            if full_text:
                with open(os.path.join(doc_dir, "full_text.txt"), "w", encoding="utf-8") as f:
                    f.write(full_text)

            # Save raw original binary file
            raw_filename = upload.filename or "file"
            with open(os.path.join(doc_dir, raw_filename), "wb") as f:
                f.write(content)
        except Exception as blob_err:
            logger.warning("Failed to write rag doc blob for doc %s: %s", doc.id, blob_err)

        # Background: chunk + embed
        background_tasks.add_task(process_document, doc.id, content, mime, upload.filename or "file", db)

        # Link to active plan if one exists
        background_tasks.add_task(_link_doc_to_plan, session_id, doc.id)

        results.append({
            "doc_id": doc.id,
            "filename": doc.filename,
            "size_bytes": doc.size_bytes,
            "status": doc.status.value,
            "preview": preview[:200],
            "ok": True,
        })

    return {"uploaded": results}


@router.get("/documents")
def list_documents(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
):
    """List all documents uploaded in this session."""
    _get_session_or_404(db, agent_id, session_id)
    docs = (
        db.query(RagDocument)
        .filter(RagDocument.session_id == session_id, RagDocument.agent_id == agent_id)
        .order_by(RagDocument.created_at.asc())
        .all()
    )
    return [
        {
            "doc_id": d.id,
            "filename": d.filename,
            "mime_type": d.mime_type,
            "size_bytes": d.size_bytes,
            "status": d.status.value,
            "chunk_count": d.chunk_count,
            "preview": d.extracted_preview,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(
    request: Request,
    agent_id: int,
    session_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
):
    """Remove a document from the session evidence pool."""
    _get_session_or_404(db, agent_id, session_id)
    doc = (
        db.query(RagDocument)
        .filter(RagDocument.id == doc_id, RagDocument.session_id == session_id)
        .first()
    )
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()
