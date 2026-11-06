def _bind():
    import app.nova.http.attachments.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
