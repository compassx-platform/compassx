"""Jupyter / EG proxy — routes all kernel REST + WebSocket traffic through the backend.

Handlers stay here. Each one forwards to one application type.
``register_kernel_resource`` stays importable from this module.
"""
import logging

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import Response

from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.notebooks.kernel.application.proxy_api_info import proxy_api_info as proxy_api_info_action
from app.notebooks.kernel.application.proxy_kernel_delete import proxy_kernel_delete as proxy_kernel_delete_action
from app.notebooks.kernel.application.proxy_kernel_get import proxy_kernel_get as proxy_kernel_get_action
from app.notebooks.kernel.application.proxy_kernel_restart import proxy_kernel_restart as proxy_kernel_restart_action
from app.notebooks.kernel.application.proxy_kernel_restart_post import (
    proxy_kernel_restart_post as proxy_kernel_restart_post_action,
)
from app.notebooks.kernel.application.proxy_kernel_ws import proxy_kernel_ws as proxy_kernel_ws_action
from app.notebooks.kernel.application.proxy_kernels_list import proxy_kernels_list as proxy_kernels_list_action
from app.notebooks.kernel.application.proxy_kernels_start import proxy_kernels_start as proxy_kernels_start_action
from app.notebooks.kernel.application.proxy_kernelspecs import proxy_kernelspecs as proxy_kernelspecs_action
from app.notebooks.kernel.registry import (
    _KERNEL_TO_RESOURCE,
    _authorize_kernel,
    _authorize_resource,
    _eg_http_url,
    _eg_ws_url,
    _kernel_catalog_api_url,
    _kernel_models,
    _resource_id_of,
    register_kernel_resource,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/notebook/jupyter",
    tags=["jupyter-proxy"],
)
http_router = APIRouter(
    dependencies=[Depends(get_guard)],
)


@router.websocket("/api/kernels/{kernel_id}/channels")
async def proxy_kernel_ws(websocket: WebSocket, kernel_id: str) -> None:
    """Bridge browser WebSocket ↔ Enterprise Gateway kernel channel."""
    await proxy_kernel_ws_action(websocket, kernel_id)


@http_router.get("/api")
async def proxy_api_info(request: Request) -> Response:
    """EG version banner. Members only, via the router guard."""
    return await proxy_api_info_action(request)


@http_router.get("/api/kernelspecs")
async def proxy_kernelspecs(request: Request) -> Response:
    """The kernel types this deployment offers. Members only."""
    return await proxy_kernelspecs_action(request)


@http_router.get("/api/kernels")
async def proxy_kernels_list(
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    """List the kernels running on compute this caller may use."""
    return await proxy_kernels_list_action(guard, db)


@http_router.post("/api/kernels")
async def proxy_kernels_start(
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    return await proxy_kernels_start_action(request, guard, db)


@http_router.get("/api/kernels/{kernel_id}")
async def proxy_kernel_get(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    return await proxy_kernel_get_action(kernel_id, request, guard, db)


@http_router.delete("/api/kernels/{kernel_id}")
async def proxy_kernel_delete(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    """Shut a kernel down."""
    return await proxy_kernel_delete_action(kernel_id, request, guard, db)


@http_router.patch("/api/kernels/{kernel_id}")
async def proxy_kernel_restart(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    return await proxy_kernel_restart_action(kernel_id, request, guard, db)


@http_router.post("/api/kernels/{kernel_id}/restart")
async def proxy_kernel_restart_post(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    """Restart a kernel."""
    return await proxy_kernel_restart_post_action(kernel_id, request, guard, db)


router.include_router(http_router)
