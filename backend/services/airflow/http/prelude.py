"""Airflow service API endpoints.

Prefix /api/v1/services/airflow applied in main.py.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.airflow.manager import get_airflow_manager

logger = logging.getLogger("services.airflow.router")
router = APIRouter(tags=["airflow"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )








