def _bind():
    import services.omnigent.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def omnigent_status():
    """Get Databricks Omnigent server status."""
    try:
        status = get_omnigent_manager().get_status()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error getting Omnigent server status")
        return _error("InternalError", str(exc), 500)
