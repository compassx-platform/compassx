from __future__ import annotations

def _bind():
    import services.airflow.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def airflow_status():
    """Get Airflow deployment status."""
    try:
        status = get_airflow_manager().get_status()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error getting Airflow status")
        return _error("InternalError", str(exc), 500)
