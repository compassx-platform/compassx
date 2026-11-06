from __future__ import annotations

def _bind():
    import services.airflow.http.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def restart_airflow():
    """Restart Airflow."""
    try:
        status = get_airflow_manager().restart()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error restarting Airflow")
        return _error("InternalError", str(exc), 500)
