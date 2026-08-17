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

logger = logging.getLogger(__name__)
router = APIRouter(tags=["enterprise-gateway"])


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


def _eg_base_url() -> str:
    return eg_settings.internal_url()


# ── Service lifecycle ─────────────────────────────────────────────────────────

@router.post("/start")
def start_eg():
    """Start Enterprise Gateway pod."""
    try:
        status = get_eg_manager().start()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error starting EG")
        return _error("InternalError", str(exc), 500)


@router.post("/stop")
def stop_eg():
    """Stop Enterprise Gateway pod."""
    try:
        status = get_eg_manager().stop()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error stopping EG")
        return _error("InternalError", str(exc), 500)


@router.post("/restart")
def restart_eg():
    """Restart Enterprise Gateway pod."""
    try:
        status = get_eg_manager().restart()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error restarting EG")
        return _error("InternalError", str(exc), 500)


@router.get("/status")
def eg_status():
    """Get Enterprise Gateway deployment status."""
    try:
        status = get_eg_manager().get_status()
        return {"phase": status.phase, "message": status.message}
    except Exception as exc:
        logger.exception("Error getting EG status")
        return _error("InternalError", str(exc), 500)


# ── Kernel proxy endpoints ────────────────────────────────────────────────────

@router.get("/kernels")
async def list_kernels():
    """List active kernels (proxied from EG)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(f"{_eg_base_url()}/api/kernels")
            return resp.json()
    except Exception as exc:
        logger.warning("EG /api/kernels failed: %s", exc)
        return _error("EGUnreachable", "Enterprise Gateway not reachable.", 503)


@router.get("/kernels/{kernel_id}")
async def get_kernel(kernel_id: str):
    """Get kernel status."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(f"{_eg_base_url()}/api/kernels/{kernel_id}")
            if resp.status_code == 404:
                return _error("NotFound", f"Kernel {kernel_id} not found.", 404)
            return resp.json()
    except Exception as exc:
        logger.warning("EG kernel status failed: %s", exc)
        return _error("EGUnreachable", "Enterprise Gateway not reachable.", 503)


@router.delete("/kernels/{kernel_id}")
async def shutdown_kernel(kernel_id: str):
    """Shutdown a kernel."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.delete(f"{_eg_base_url()}/api/kernels/{kernel_id}")
            if resp.status_code == 404:
                return _error("NotFound", f"Kernel {kernel_id} not found.", 404)
            return {"shutdown": True, "kernel_id": kernel_id}
    except Exception as exc:
        logger.warning("EG kernel shutdown failed: %s", exc)
        return _error("EGUnreachable", "Enterprise Gateway not reachable.", 503)


@router.get("/kernelspecs")
async def list_kernelspecs():
    """List available kernelspecs for UI dropdown."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(f"{_eg_base_url()}/api/kernelspecs")
            if resp.status_code != 200:
                return _error("EGError", "Could not fetch kernelspecs.", resp.status_code)
            return resp.json()
    except Exception as exc:
        logger.warning("EG kernelspecs failed: %s", exc)
        return _error("EGUnreachable", "Enterprise Gateway not reachable.", 503)
