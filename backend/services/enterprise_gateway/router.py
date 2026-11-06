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








from services.enterprise_gateway.http.application.start_eg import start_eg as start_eg_action
from services.enterprise_gateway.http.application.stop_eg import stop_eg as stop_eg_action
from services.enterprise_gateway.http.application.restart_eg import restart_eg as restart_eg_action
from services.enterprise_gateway.http.application.eg_status import eg_status as eg_status_action
from services.enterprise_gateway.http.application.list_kernels import list_kernels as list_kernels_action
from services.enterprise_gateway.http.application.get_kernel import get_kernel as get_kernel_action
from services.enterprise_gateway.http.application.shutdown_kernel import shutdown_kernel as shutdown_kernel_action
from services.enterprise_gateway.http.application.list_kernelspecs import list_kernelspecs as list_kernelspecs_action

@router.post("/start")
def start_eg():
    """Start Enterprise Gateway pod."""
    return start_eg_action()

@router.post("/stop")
def stop_eg():
    """Stop Enterprise Gateway pod."""
    return stop_eg_action()

@router.post("/restart")
def restart_eg():
    """Restart Enterprise Gateway pod."""
    return restart_eg_action()

@router.get("/status")
def eg_status():
    """Get Enterprise Gateway deployment status."""
    return eg_status_action()

@router.get("/kernels")
async def list_kernels():
    """List active kernels (proxied from EG)."""
    return await list_kernels_action()

@router.get("/kernels/{kernel_id}")
async def get_kernel(kernel_id: str):
    """Get kernel status."""
    return await get_kernel_action(kernel_id=kernel_id)

@router.delete("/kernels/{kernel_id}")
async def shutdown_kernel(kernel_id: str):
    """Shutdown a kernel."""
    return await shutdown_kernel_action(kernel_id=kernel_id)

@router.get("/kernelspecs")
async def list_kernelspecs():
    """List available kernelspecs for UI dropdown."""
    return await list_kernelspecs_action()

