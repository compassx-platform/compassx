from __future__ import annotations

def _bind():
    import services.jupyter_server.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def jupyter_server_status():
    """Get Jupyter Server deployment status."""
    try:
        status = get_js_manager().get_status()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error getting Jupyter Server status")
        return _error("InternalError", str(exc), 500)
