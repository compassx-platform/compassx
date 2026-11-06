def _bind():
    import services.omnigent.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def restart_omnigent():
    """Restart Databricks Omnigent server service."""
    try:
        status = get_omnigent_manager().restart()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error restarting Omnigent server")
        return _error("InternalError", str(exc), 500)
