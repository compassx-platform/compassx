def _bind():
    import app.ai_gateway.http.endpoints.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_endpoint(
    endpoint_id: int,
    body: AIModelEndpointUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update AI Model Endpoint."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    ws_id = _get_workspace_id(request)
    if body.is_default and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"is_default": False})

    if body.use_for_embedding and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"use_for_embedding": False})

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(endpoint, field, value)

    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)
