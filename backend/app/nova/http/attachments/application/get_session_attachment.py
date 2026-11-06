def _bind():
    import app.nova.http.attachments.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
