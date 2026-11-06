from __future__ import annotations

def _bind():
    import services.jupyter_server.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def stop_jupyter_server():
    """Stop Jupyter Server pod."""
    try:
        status = get_js_manager().stop()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error stopping Jupyter Server")
        return _error("InternalError", str(exc), 500)
