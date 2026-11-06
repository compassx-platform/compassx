"""Jupyter Server service API endpoints.

Prefix /api/v1/services/jupyter-server applied in main.py.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.jupyter_server.manager import get_js_manager

logger = logging.getLogger("services.jupyter_server.router")
router = APIRouter(tags=["jupyter-server"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )









from services.jupyter_server.http.application.start_jupyter_server import start_jupyter_server as start_jupyter_server_action
from services.jupyter_server.http.application.stop_jupyter_server import stop_jupyter_server as stop_jupyter_server_action
from services.jupyter_server.http.application.restart_jupyter_server import restart_jupyter_server as restart_jupyter_server_action
from services.jupyter_server.http.application.jupyter_server_status import jupyter_server_status as jupyter_server_status_action

@router.post("/start")
def start_jupyter_server():
    """Start Jupyter Server pod (also starts EG if needed)."""
    return start_jupyter_server_action()

@router.post("/stop")
def stop_jupyter_server():
    """Stop Jupyter Server pod."""
    return stop_jupyter_server_action()

@router.post("/restart")
def restart_jupyter_server():
    """Restart Jupyter Server pod."""
    return restart_jupyter_server_action()

@router.get("/status")
def jupyter_server_status():
    """Get Jupyter Server deployment status."""
    return jupyter_server_status_action()

