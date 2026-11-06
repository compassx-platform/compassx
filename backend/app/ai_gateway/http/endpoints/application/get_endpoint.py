def _bind():
    import app.ai_gateway.http.endpoints.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get AI Model Endpoint by ID."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return _to_endpoint_response(endpoint)
