def _bind():
    import services.omnigent.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def suspend_omnigent():
    """Suspend Databricks Omnigent server service (scale to zero replicas, keep volumes)."""
    try:
        status = get_omnigent_manager().suspend()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error suspending Omnigent server")
        return _error("InternalError", str(exc), 500)
