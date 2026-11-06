def _bind():
    import app.ai_gateway.http.endpoints.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def set_default_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Set endpoint as the default model endpoint for the workspace."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    ws_id = _get_workspace_id(request)
    if ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"is_default": False})
    endpoint.is_default = True
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)
