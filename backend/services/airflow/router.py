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









from services.airflow.http.application.start_airflow import start_airflow as start_airflow_action
from services.airflow.http.application.stop_airflow import stop_airflow as stop_airflow_action
from services.airflow.http.application.restart_airflow import restart_airflow as restart_airflow_action
from services.airflow.http.application.airflow_status import airflow_status as airflow_status_action

@router.post("/start")
def start_airflow():
    """Start Airflow."""
    return start_airflow_action()

@router.post("/stop")
def stop_airflow():
    """Stop Airflow."""
    return stop_airflow_action()

@router.post("/restart")
def restart_airflow():
    """Restart Airflow."""
    return restart_airflow_action()

@router.get("/status")
def airflow_status():
    """Get Airflow deployment status."""
    return airflow_status_action()

