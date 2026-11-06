def _bind():
    import app.agents.http.documents.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_document(
    request: Request,
    agent_id: int,
    session_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a document from the session evidence pool.

    EXECUTE, the same as adding one: both change what the agent will read on
    the next turn.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    doc = (
        db.query(RagDocument)
        .filter(RagDocument.id == doc_id, RagDocument.session_id == session_id)
        .first()
    )
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()
