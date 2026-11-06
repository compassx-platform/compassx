from __future__ import annotations

def _bind():
    import services.jupyter_server.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def restart_jupyter_server():
    """Restart Jupyter Server pod."""
    try:
        status = get_js_manager().restart()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error restarting Jupyter Server")
        return _error("InternalError", str(exc), 500)
