def _bind():
    import services.omnigent.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def start_omnigent():
    """Start Databricks Omnigent server service on-demand."""
    try:
        from app.services.sandbox_reaper_service import unified_reaper_service
        unified_reaper_service.touch_omnigent_activity()
        status = get_omnigent_manager().start()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error starting Omnigent server")
        return _error("InternalError", str(exc), 500)
