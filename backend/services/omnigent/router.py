"""Databricks Omnigent service API endpoints.

Prefix /api/v1/services/omnigent applied in main.py.
"""
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.omnigent.manager import get_omnigent_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["omnigent"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


@router.post("/start")
def start_omnigent():
    """Start Databricks Omnigent server service on-demand."""
    try:
        status = get_omnigent_manager().start()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error starting Omnigent server")
        return _error("InternalError", str(exc), 500)


@router.post("/stop")
def stop_omnigent():
    """Stop Databricks Omnigent server service."""
    try:
        status = get_omnigent_manager().stop()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error stopping Omnigent server")
        return _error("InternalError", str(exc), 500)


@router.post("/restart")
def restart_omnigent():
    """Restart Databricks Omnigent server service."""
    try:
        status = get_omnigent_manager().restart()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error restarting Omnigent server")
        return _error("InternalError", str(exc), 500)


@router.get("/status")
def omnigent_status():
    """Get Databricks Omnigent server status."""
    try:
        status = get_omnigent_manager().get_status()
        return {"phase": status.phase, "message": status.message, "details": status.details}
    except Exception as exc:
        logger.exception("Error getting Omnigent server status")
        return _error("InternalError", str(exc), 500)
