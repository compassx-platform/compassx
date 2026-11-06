def _bind():
    import app.nova.http.attachments.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
