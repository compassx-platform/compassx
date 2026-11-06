def _bind():
    import app.agents.http.documents.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def upload_documents(
    request: Request,
    agent_id: int,
    session_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Upload one or more documents to the session evidence pool (Part F2).

    EXECUTE: an uploaded file is chunked, embedded, and fed to the agent on
    the next turn, so this is supplying input to a run rather than storing a
    file. Whoever may run the agent may give it something to read.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)

    all_uploads: list[UploadFile] = list(files or [])
    try:
        form = await request.form()
        for field in ("file", "files"):
            for item in form.getlist(field):
                if isinstance(item, UploadFile) and item not in all_uploads:
                    all_uploads.append(item)
    except Exception:
        pass

    if not all_uploads:
        raise HTTPException(400, "No files uploaded")

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
    for upload in all_uploads:
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
