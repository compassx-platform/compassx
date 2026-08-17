"""Jupyter Server service API endpoints.

Prefix /api/v1/services/jupyter-server applied in main.py.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.jupyter_server.manager import get_js_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jupyter-server"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


@router.post("/start")
def start_jupyter_server():
    """Start Jupyter Server pod (also starts EG if needed)."""
    try:
        status = get_js_manager().start()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error starting Jupyter Server")
        return _error("InternalError", str(exc), 500)


@router.post("/stop")
def stop_jupyter_server():
    """Stop Jupyter Server pod."""
    try:
        status = get_js_manager().stop()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error stopping Jupyter Server")
        return _error("InternalError", str(exc), 500)


@router.post("/restart")
def restart_jupyter_server():
    """Restart Jupyter Server pod."""
    try:
        status = get_js_manager().restart()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error restarting Jupyter Server")
        return _error("InternalError", str(exc), 500)


@router.get("/status")
def jupyter_server_status():
    """Get Jupyter Server deployment status."""
    try:
        status = get_js_manager().get_status()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error getting Jupyter Server status")
        return _error("InternalError", str(exc), 500)
