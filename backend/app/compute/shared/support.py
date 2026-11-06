"""Shared compute request checks. Logs stay on the route logger."""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from compute.config import compute_settings
from compassx.lookup import try_resolve_url_container
from compute.schemas import ComputeServiceInfo

logger = logging.getLogger("app.compute.routes.router")
_STATUS_TIMEOUT_SECONDS = 3

try:
    from sse_starlette.sse import EventSourceResponse

    _SSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    EventSourceResponse = None
    _SSE_AVAILABLE = False


def _kernel_catalog_api_url() -> str:
    """Return a catalog URL that notebook kernels can reach from containers/pods."""
    return try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"


def _service(req_context: Request, db):
    """Build the resource service with the platform RuntimeManager injected."""
    from app.compute.services.resource_service import platform_enabled
    from app.dependencies import get_runtime_manager
    from compute.resource_service import ComputeResourceService

    runtime_manager = None
    if platform_enabled():
        try:
            runtime_manager = get_runtime_manager(req_context)
        except Exception:
            logger.exception("Platform runtime manager unavailable; using legacy path")
    return ComputeResourceService(db, runtime_manager=runtime_manager)


def _error(error_type: str, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"error": error_type, "message": message, "code": code},
    )


def _caller(req_context: Request, guard: Guard) -> tuple[str, str]:
    """The (user_id, workspace_id) a compute request acts as."""
    ctx = getattr(req_context.state, "workspace", None)
    if ctx is None:
        raise HTTPException(
            status_code=400,
            detail="No workspace context. Address this endpoint under /w/<workspace>.",
        )
    return str(guard.principal.id), str(ctx.workspace_id)


def _is_default_compute(db, resource_id: str) -> bool:
    from app.models.compute_resources import ComputeResource

    return bool(
        db.query(ComputeResource.id)
        .filter(
            ComputeResource.id == resource_id,
            ComputeResource.is_default.is_(True),
        )
        .first()
    )


def _require_compute(guard: Guard, db, resource_id: str, privilege: Privilege) -> None:
    """Enforce ``privilege`` on a compute resource, excepting the default."""
    securable = Securable.compute(resource_id)
    if privilege in (Privilege.BROWSE, Privilege.USE_COMPUTE) and _is_default_compute(
        db, resource_id
    ):
        return
    guard.require(privilege, securable)


def _active_driver(req_context: Request) -> str:
    """Return the active compute driver ('docker', 'kubernetes', 'local')."""
    from app.compute.services.resource_service import platform_enabled
    from app.dependencies import get_runtime_manager

    if platform_enabled():
        try:
            rm = get_runtime_manager(req_context)
            if rm and hasattr(rm, "resource_manager"):
                driver = getattr(rm.resource_manager, "default_driver", None)
                if driver:
                    return str(driver)
        except Exception:
            pass
    return "kubernetes" if compute_settings.is_k8s() else "docker"


def _service_info(service_id: str, label: str, status) -> ComputeServiceInfo:
    return ComputeServiceInfo(
        id=service_id,
        label=label,
        phase=status.phase.value if hasattr(status.phase, "value") else str(status.phase),
        message=status.message,
        details=status.details,
    )


def _run_service_action_async(service_name: str, action: str, label: str, manager) -> None:
    logger.info("compute-service: %s %s requested", service_name, action)
    try:
        status = getattr(manager, action)()
        logger.info(
            "compute-service: %s %s completed phase=%s message=%s",
            service_name,
            action,
            status.phase.value if hasattr(status.phase, "value") else str(status.phase),
            status.message,
        )
    except Exception:
        logger.exception("compute-service: %s %s failed", service_name, action)
