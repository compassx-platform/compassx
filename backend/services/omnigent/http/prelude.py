"""Databricks Omnigent service API endpoints.

Prefix /api/v1/services/omnigent applied in main.py.
"""
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.omnigent.manager import get_omnigent_manager

logger = logging.getLogger("services.omnigent.router")


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )












