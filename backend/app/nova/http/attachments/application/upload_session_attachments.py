def _bind():
    import app.nova.http.attachments.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
