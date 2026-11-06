def _bind():
    import app.nova.http.attachments.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
