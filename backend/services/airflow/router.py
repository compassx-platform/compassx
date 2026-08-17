"""Airflow service API endpoints.

Prefix /api/v1/services/airflow applied in main.py.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.airflow.manager import get_airflow_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["airflow"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


@router.post("/start")
def start_airflow():
    """Start Airflow."""
    try:
        status = get_airflow_manager().start()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error starting Airflow")
        return _error("InternalError", str(exc), 500)


@router.post("/stop")
def stop_airflow():
    """Stop Airflow."""
    try:
        status = get_airflow_manager().stop()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error stopping Airflow")
        return _error("InternalError", str(exc), 500)


@router.post("/restart")
def restart_airflow():
    """Restart Airflow."""
    try:
        status = get_airflow_manager().restart()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error restarting Airflow")
        return _error("InternalError", str(exc), 500)


@router.get("/status")
def airflow_status():
    """Get Airflow deployment status."""
    try:
        status = get_airflow_manager().get_status()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error getting Airflow status")
        return _error("InternalError", str(exc), 500)
