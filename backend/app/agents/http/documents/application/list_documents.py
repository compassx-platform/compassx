def _bind():
    import app.agents.http.documents.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_documents(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List all documents uploaded in this session.

    BROWSE: the response carries each file's extracted preview, which is its
    content.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
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
