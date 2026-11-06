def _bind():
    import app.ai_gateway.http.endpoints.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_endpoints(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all AI Model Endpoints for the workspace."""
    ws_id = _get_workspace_id(request)
    query = db.query(AIModelEndpoint)
    if ws_id:
        query = query.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
    endpoints = query.order_by(AIModelEndpoint.name).all()
    return [_to_endpoint_response(ep) for ep in endpoints]
