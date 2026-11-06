"""Databricks Omnigent service API endpoints.

Prefix /api/v1/services/omnigent applied in main.py.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from services.omnigent.manager import get_omnigent_manager

import services.omnigent.http.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from services.omnigent.http.application.start_omnigent import start_omnigent as start_omnigent_action
from services.omnigent.http.application.suspend_omnigent import suspend_omnigent as suspend_omnigent_action
from services.omnigent.http.application.resume_omnigent import resume_omnigent as resume_omnigent_action
from services.omnigent.http.application.stop_omnigent import stop_omnigent as stop_omnigent_action
from services.omnigent.http.application.restart_omnigent import restart_omnigent as restart_omnigent_action
from services.omnigent.http.application.omnigent_status import omnigent_status as omnigent_status_action

router = APIRouter(tags=["omnigent"])

@router.post("/start")
def start_omnigent():
    """Start Databricks Omnigent server service on-demand."""
    return start_omnigent_action()

@router.post("/suspend")
def suspend_omnigent():
    """Suspend Databricks Omnigent server service (scale to zero replicas, keep volumes)."""
    return suspend_omnigent_action()

@router.post("/resume")
def resume_omnigent():
    """Resume suspended Databricks Omnigent server service (scale back to 1 replica)."""
    return resume_omnigent_action()

@router.post("/stop")
def stop_omnigent():
    """Stop Databricks Omnigent server service."""
    return stop_omnigent_action()

@router.post("/restart")
def restart_omnigent():
    """Restart Databricks Omnigent server service."""
    return restart_omnigent_action()

@router.get("/status")
def omnigent_status():
    """Get Databricks Omnigent server status."""
    return omnigent_status_action()

