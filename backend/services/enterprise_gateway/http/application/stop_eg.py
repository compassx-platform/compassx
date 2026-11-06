from __future__ import annotations

def _bind():
    import services.enterprise_gateway.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def stop_eg():
    """Stop Enterprise Gateway pod."""
    try:
        status = get_eg_manager().stop()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error stopping EG")
        return _error("InternalError", str(exc), 500)
