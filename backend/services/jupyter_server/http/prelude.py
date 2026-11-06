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








