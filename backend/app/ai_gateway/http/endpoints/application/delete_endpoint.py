def _bind():
    import app.ai_gateway.http.endpoints.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an AI Model Endpoint."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    db.delete(endpoint)
    db.commit()
    return None
