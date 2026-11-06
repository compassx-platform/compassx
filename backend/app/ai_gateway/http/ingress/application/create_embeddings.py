def _bind():
    import app.ai_gateway.http.ingress.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def create_embeddings(
    body: EmbeddingRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI-compatible vector embeddings endpoint."""
    texts = [body.input] if isinstance(body.input, str) else body.input
    workspace_id, caller_type, caller_id = _resolve_caller_and_workspace(request)

    try:
        raw_embeddings = await GatewayService.embed(
            db=db,
            texts=texts,
            model_name_or_id=body.model,
            workspace_id=workspace_id,
        )
        data_items = [
            EmbeddingData(object="embedding", index=i, embedding=emb)
            for i, emb in enumerate(raw_embeddings)
        ]
        return EmbeddingResponse(
            data=data_items,
            model=body.model,
        )
    except Exception as exc:
        logger.error("Embedding generation error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
