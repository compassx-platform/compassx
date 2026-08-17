"""Nova File Attachment Service — Upload, Storage, Extraction & Context Delivery.

Implements architecture/agents/file-attachments-spec.md
"""

from __future__ import annotations

import base64
import io
import logging
import os
import uuid
from typing import Any, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.agents import NovaAttachment, NovaAttachmentPreview

logger = logging.getLogger(__name__)

# Spec default caps and thresholds
D8_TOKEN_THRESHOLD = 3000          # Below threshold -> inline, Above threshold -> tool_fetch
D9_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
D10_MAX_CONCURRENT_ATTACHMENTS = 10
D11_PREVIEW_MAX_LINES = 100
D11_PREVIEW_MAX_ROWS = 50

# Storage root directory for Nova attachments
STORAGE_BASE_DIR = os.environ.get("NOVA_ATTACHMENT_STORAGE_DIR", os.path.join(".compassx", "nova_storage"))


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _get_attachment_blob_path(session_id: int, file_id: uuid.UUID, filename: str) -> str:
    return os.path.join(STORAGE_BASE_DIR, "sessions", str(session_id), "uploads", str(file_id), filename)


def _get_extracted_blob_path(session_id: int, file_id: uuid.UUID) -> str:
    return os.path.join(STORAGE_BASE_DIR, "sessions", str(session_id), "extracted", str(file_id), "full_text.txt")


def _post_process_pdf_text(text: str) -> str:
    """Format raw PDF layout text streams into clean markdown tables."""
    import re
    lines = text.splitlines()
    processed = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.search(r'\bRE\b.*\bAC\b.*\bDC\b', line, re.IGNORECASE) or re.search(r'\bSite\b.*\bCapacity\b', line, re.IGNORECASE):
            headers = [h for h in re.split(r'\s{2,}|\t', line) if h]
            if len(headers) >= 2:
                processed.append('\n| ' + ' | '.join(headers) + ' |')
                processed.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                i += 1
                while i < len(lines):
                    d_line = lines[i].strip()
                    if not d_line or d_line.startswith('=== Page'):
                        break
                    parts = [p for p in re.split(r'\s{2,}|\t', d_line) if p]
                    if len(parts) < 2:
                        parts = d_line.split()
                    if len(parts) >= 2:
                        processed.append('| ' + ' | '.join(parts) + ' |')
                        i += 1
                    else:
                        break
                continue
        processed.append(lines[i])
        i += 1
    return '\n'.join(processed)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Upload Service Function
# ─────────────────────────────────────────────────────────────────────────────

def upload_attachment(
    session_id: int,
    user_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    db: Session,
) -> NovaAttachment:
    """Validate, store, and record a new session file attachment."""
    # Check D9 max file size
    if len(file_bytes) > D9_MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size ({len(file_bytes)} bytes) exceeds the maximum allowed size of {D9_MAX_FILE_SIZE_BYTES // (1024*1024)} MB",
        )

    # Check D10 max concurrent attachments per session
    existing_count = (
        db.query(NovaAttachment)
        .filter(NovaAttachment.session_id == session_id, NovaAttachment.status != "purged")
        .count()
    )
    if existing_count >= D10_MAX_CONCURRENT_ATTACHMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum concurrent attachments limit ({D10_MAX_CONCURRENT_ATTACHMENTS}) reached for this session.",
        )

    file_id = uuid.uuid4()
    blob_path = _get_attachment_blob_path(session_id, file_id, filename)

    # Save raw file bytes
    _ensure_dir(blob_path)
    with open(blob_path, "wb") as f:
        f.write(file_bytes)

    # Insert DB record (status=processing)
    attachment = NovaAttachment(
        file_id=file_id,
        session_id=session_id,
        filename=filename,
        mime_type=mime_type or "application/octet-stream",
        size_bytes=len(file_bytes),
        blob_path=blob_path,
        status="processing",
        created_by=user_id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    # Run extraction synchronously or background
    extract_attachment(file_id, db)
    db.refresh(attachment)
    return attachment


# ─────────────────────────────────────────────────────────────────────────────
# 2. Extraction Worker Function
# ─────────────────────────────────────────────────────────────────────────────

def extract_attachment(file_id: uuid.UUID, db: Session) -> None:
    """Extract content, decide delivery_mode, compute preview, and store text blob."""
    attachment = db.query(NovaAttachment).filter(NovaAttachment.file_id == file_id).first()
    if not attachment:
        logger.error("Attachment %s not found for extraction", file_id)
        return

    try:
        if not os.path.exists(attachment.blob_path):
            raise FileNotFoundError(f"Blob file not found at {attachment.blob_path}")

        with open(attachment.blob_path, "rb") as f:
            content = f.read()

        filename = attachment.filename
        mime_type = attachment.mime_type.lower()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        extracted_text = ""
        delivery_mode = "inline"
        is_image = mime_type.startswith("image/") or ext in ("png", "jpg", "jpeg", "webp", "gif", "svg")

        if is_image:
            delivery_mode = "multimodal_native"
            extracted_text = f"[Image file: {filename}, size: {len(content)} bytes]"
        elif mime_type == "application/pdf" or ext == "pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content))
                num_pages = len(reader.pages)
                pages_text = []
                page_summaries = []
                for idx, page in enumerate(reader.pages):
                    p_text = ""
                    try:
                        p_text = page.extract_text(extraction_mode="layout") or ""
                    except Exception:
                        p_text = page.extract_text() or ""
                    p_text = _post_process_pdf_text(p_text)
                    # Extract first non-empty header/title line for page index
                    first_line = next((line.strip() for line in p_text.splitlines() if line.strip() and not line.startswith("===")), f"Page {idx + 1}")
                    page_summaries.append(f"  - Page {idx + 1} of {num_pages}: {first_line[:90]}")
                    pages_text.append(f"=== Page {idx + 1} of {num_pages} ===\n" + p_text)
                
                outline = "Document Outline / Page Index:\n" + "\n".join(page_summaries)
                extracted_text = f"[PDF Document: {filename} | Total Pages: {num_pages}]\n{outline}\n\n" + "\n\n".join(pages_text)
            except Exception as e:
                logger.warning("PDF extraction fallback for %s: %s", filename, e)
                extracted_text = content.decode("utf-8", errors="replace")
        elif mime_type in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel") or ext in ("xlsx", "xls"):
            try:
                import pandas as pd
                excel_file = pd.ExcelFile(io.BytesIO(content))
                sheets_text = []
                for sheet in excel_file.sheet_names:
                    df = excel_file.parse(sheet)
                    sheets_text.append(f"--- Sheet: {sheet} (rows: {len(df)}, cols: {len(df.columns)}) ---\n" + df.to_csv(index=False))
                extracted_text = "\n\n".join(sheets_text)
            except Exception as e:
                logger.warning("Excel extraction fallback for %s: %s", filename, e)
                extracted_text = content.decode("utf-8", errors="replace")
        elif mime_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) or ext == "docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(content))
                extracted_text = "\n".join(p.text for p in doc.paragraphs)
            except Exception as e:
                logger.warning("Docx extraction fallback for %s: %s", filename, e)
                extracted_text = content.decode("utf-8", errors="replace")
        else:
            # Plain text / code / CSV / markdown / JSON
            extracted_text = content.decode("utf-8", errors="replace")

        # Compute token estimate (~4 chars per token)
        token_count = max(1, len(extracted_text) // 4)

        if not is_image:
            if token_count <= D8_TOKEN_THRESHOLD:
                delivery_mode = "inline"
            else:
                delivery_mode = "tool_fetch"

        # Generate preview text per D11
        lines = extracted_text.splitlines()
        if len(lines) <= D11_PREVIEW_MAX_LINES:
            preview_text = "\n".join(lines)
        else:
            # Check for page markers === Page X of Y ===
            page_markers = [i for i, line in enumerate(lines) if line.startswith("=== Page ")]
            if len(page_markers) > 1:
                lines_per_page = max(4, D11_PREVIEW_MAX_LINES // len(page_markers))
                preview_parts = [
                    f"[Multi-Page Document Preview ({len(page_markers)} pages total). Call fetch_attachment(file_id='{file_id}', page=N) or fetch_attachment(file_id='{file_id}') to inspect full text.]"
                ]
                for p_idx, line_num in enumerate(page_markers):
                    next_line_num = page_markers[p_idx + 1] if p_idx + 1 < len(page_markers) else len(lines)
                    page_chunk = lines[line_num:min(line_num + lines_per_page + 1, next_line_num)]
                    preview_parts.append("\n".join(page_chunk))
                preview_text = "\n\n".join(preview_parts)
                if len(lines) > D11_PREVIEW_MAX_LINES:
                    preview_text += f"\n\n... [{len(lines)} total lines extracted across {len(page_markers)} pages. Use fetch_attachment tool to inspect full content]"
            else:
                preview_lines = lines[:D11_PREVIEW_MAX_LINES]
                preview_text = "\n".join(preview_lines) + f"\n... [{len(lines) - D11_PREVIEW_MAX_LINES} more lines truncated. Use fetch_attachment tool to inspect full content]"

        # Store full text blob for tool_fetch
        full_text_blob_path = _get_extracted_blob_path(attachment.session_id, file_id)
        _ensure_dir(full_text_blob_path)
        with open(full_text_blob_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)

        # Update Attachment DB record
        attachment.status = "ready"
        attachment.delivery_mode = delivery_mode
        attachment.extracted_token_count = token_count
        attachment.extraction_error = None

        # Upsert Preview record
        preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == file_id).first()
        if not preview_rec:
            preview_rec = NovaAttachmentPreview(
                file_id=file_id,
                preview_text=preview_text,
                full_text_blob_path=full_text_blob_path,
            )
            db.add(preview_rec)
        else:
            preview_rec.preview_text = preview_text
            preview_rec.full_text_blob_path = full_text_blob_path

        db.commit()
        logger.info("Extracted attachment %s: mode=%s, tokens=%d", file_id, delivery_mode, token_count)

    except Exception as exc:
        logger.exception("Extraction failed for attachment %s", file_id)
        attachment.status = "failed"
        attachment.extraction_error = str(exc)
        db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Context Payload Assembly
# ─────────────────────────────────────────────────────────────────────────────

def get_context_payload(file_id: uuid.UUID, db: Session) -> dict[str, Any]:
    """Build Nova context payload block for turn construction."""
    attachment = db.query(NovaAttachment).filter(NovaAttachment.file_id == file_id).first()
    if not attachment:
        return {"file_id": str(file_id), "status": "error", "error": "Attachment not found"}

    if attachment.status != "ready":
        return {
            "file_id": str(file_id),
            "filename": attachment.filename,
            "status": attachment.status,
            "error": attachment.extraction_error or "File is processing or corrupt",
        }

    preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == file_id).first()
    preview_text = preview_rec.preview_text if preview_rec else ""
    full_text_path = preview_rec.full_text_blob_path if preview_rec else None

    if attachment.delivery_mode == "multimodal_native":
        # Base64 encode for native image block
        b64_content = ""
        if os.path.exists(attachment.blob_path):
            with open(attachment.blob_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
        return {
            "type": "multimodal_native",
            "file_id": str(file_id),
            "filename": attachment.filename,
            "mime_type": attachment.mime_type,
            "base64": b64_content,
        }

    if attachment.delivery_mode == "inline":
        full_text = ""
        if full_text_path and os.path.exists(full_text_path):
            with open(full_text_path, "r", encoding="utf-8") as f:
                full_text = f.read()
        return {
            "type": "inline",
            "file_id": str(file_id),
            "filename": attachment.filename,
            "mime_type": attachment.mime_type,
            "token_count": attachment.extracted_token_count,
            "content": full_text,
        }

    # tool_fetch delivery mode
    return {
        "type": "tool_fetch",
        "file_id": str(file_id),
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "token_count": attachment.extracted_token_count,
        "preview_text": preview_text,
        "instruction": f"Use fetch_attachment(file_id='{file_id}') to query or read more content from this file.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Fetch Attachment Tool Retrieval Implementation
# ─────────────────────────────────────────────────────────────────────────────

def fetch_attachment_content(
    file_id: str | int | uuid.UUID,
    query: Optional[str] = None,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    page: Optional[int | str] = None,
    db: Optional[Session] = None,
) -> str:
    """Server-side execution for fetch_attachment tool call supporting Nova attachments and Rag documents."""
    if db is None:
        from app.database import SystemSessionLocal
        temp_db = SystemSessionLocal()
        try:
            return fetch_attachment_content(file_id, query, line_start, line_end, page=page, db=temp_db)
        finally:
            temp_db.close()

    lines: list[str] = []

    # 1. Try resolving as NovaAttachment (UUID)
    file_id_uuid = None
    if isinstance(file_id, uuid.UUID):
        file_id_uuid = file_id
    elif isinstance(file_id, str):
        try:
            file_id_uuid = uuid.UUID(file_id)
        except ValueError:
            file_id_uuid = None

    if file_id_uuid:
        preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == file_id_uuid).first()
        if preview_rec and preview_rec.full_text_blob_path and os.path.exists(preview_rec.full_text_blob_path):
            with open(preview_rec.full_text_blob_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

    # 2. Try resolving as RagDocument (integer doc_id)
    if not lines:
        doc_id = None
        if isinstance(file_id, int):
            doc_id = file_id
        elif isinstance(file_id, str) and (file_id.isdigit() or (file_id.startswith("doc_") and file_id[4:].isdigit())):
            doc_id = int(file_id[4:]) if file_id.startswith("doc_") else int(file_id)

        if doc_id is not None:
            from app.models.agents import RagDocument, RagChunk
            rdoc = db.query(RagDocument).filter(RagDocument.id == doc_id).first()
            if rdoc:
                doc_blob_path = os.path.join(STORAGE_BASE_DIR, "sessions", str(rdoc.session_id), "rag_docs", str(rdoc.id), "full_text.txt")
                if os.path.exists(doc_blob_path):
                    with open(doc_blob_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                else:
                    chunks = db.query(RagChunk).filter(RagChunk.document_id == doc_id).order_by(RagChunk.chunk_index).all()
                    if chunks:
                        full_text = "".join(c.content for c in chunks)
                        lines = [l + "\n" for l in full_text.splitlines()]
                    elif rdoc.extracted_preview:
                        lines = [l + "\n" for l in rdoc.extracted_preview.splitlines()]

    if not lines:
        return f"Error: Document or attachment not found for file_id '{file_id}'"

    # Filter by page number if specified
    if page is not None and str(page).lower() != "all":
        try:
            page_num = int(page)
            p_start = None
            p_end = len(lines)
            for idx, line in enumerate(lines):
                # Check for "=== Page N of" or "=== Page N ==="
                if f"=== Page {page_num} of" in line or f"=== Page {page_num} ===" in line or line.strip().startswith(f"=== Page {page_num} "):
                    p_start = idx
                elif p_start is not None and ("=== Page " in line and line.strip().startswith("=== Page ")):
                    p_end = idx
                    break
            if p_start is not None:
                lines = lines[p_start:p_end]
            else:
                return f"Page {page_num} not found in file '{file_id}'."
        except ValueError:
            pass

    start_idx = max(0, (line_start - 1)) if line_start and line_start > 0 else 0
    end_idx = min(len(lines), line_end) if line_end and line_end > 0 else len(lines)

    sliced_lines = lines[start_idx:end_idx]

    if query and query.strip():
        q_lower = query.strip().lower()
        matched = [f"L{idx + start_idx + 1}: {line}" for idx, line in enumerate(sliced_lines) if q_lower in line.lower()]
        if not matched:
            return f"No lines matched query '{query}' in specified range L{start_idx + 1}-L{end_idx}."
        return "".join(matched)

    formatted = [f"L{idx + start_idx + 1}: {line}" for idx, line in enumerate(sliced_lines)]
    return "".join(formatted)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Promotion & Purge Functions
# ─────────────────────────────────────────────────────────────────────────────

def promote_attachment(file_id: uuid.UUID, target_catalog_path: str, user_id: str, db: Session) -> dict[str, Any]:
    """Promote session file attachment to catalog object."""
    attachment = db.query(NovaAttachment).filter(NovaAttachment.file_id == file_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    promoted_uuid = uuid.uuid4()
    attachment.promoted_object_id = promoted_uuid
    db.commit()

    return {
        "ok": True,
        "file_id": str(file_id),
        "promoted_object_id": str(promoted_uuid),
        "target_catalog_path": target_catalog_path,
        "message": f"Attachment '{attachment.filename}' promoted to catalog volume at {target_catalog_path}",
    }


def purge_session_attachments(session_id: int, db: Session) -> None:
    """Purge non-promoted file blobs on session GC."""
    attachments = (
        db.query(NovaAttachment)
        .filter(NovaAttachment.session_id == session_id, NovaAttachment.status != "purged")
        .all()
    )

    for att in attachments:
        if not att.promoted_object_id:
            # Delete uploaded raw blob if exists
            if os.path.exists(att.blob_path):
                try:
                    os.remove(att.blob_path)
                except Exception as e:
                    logger.warning("Could not remove blob %s: %s", att.blob_path, e)

            # Delete extracted text blob if exists
            preview_rec = db.query(NovaAttachmentPreview).filter(NovaAttachmentPreview.file_id == att.file_id).first()
            if preview_rec and preview_rec.full_text_blob_path and os.path.exists(preview_rec.full_text_blob_path):
                try:
                    os.remove(preview_rec.full_text_blob_path)
                except Exception as e:
                    logger.warning("Could not remove preview blob %s: %s", preview_rec.full_text_blob_path, e)

            att.status = "purged"

    db.commit()
