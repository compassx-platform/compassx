"""Enterprise Gateway service API endpoints.

Prefix /api/v1/services/enterprise-gateway applied in main.py.

These proxy kernel/kernelspec operations to EG's REST API,
keeping K8s-internal endpoints behind the CompassX backend.
"""
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from compute.config import compute_settings
from services.base import ServicePhase
from services.enterprise_gateway.config import eg_settings
from services.enterprise_gateway.manager import get_eg_manager

logger = logging.getLogger("services.enterprise_gateway.router")
router = APIRouter(tags=["enterprise-gateway"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


def _eg_base_url() -> str:
    return eg_settings.internal_url()


# ── Service lifecycle ─────────────────────────────────────────────────────────









# ── Kernel proxy endpoints ────────────────────────────────────────────────────







