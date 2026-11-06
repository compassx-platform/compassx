"""Kernel identity and the Enterprise Gateway address. Logs stay on the proxy logger."""
from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response
from starlette.websockets import WebSocket

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from compassx.lookup import try_resolve_url_container
from services.enterprise_gateway.config import eg_settings

logger = logging.getLogger("app.notebooks.routes.jupyter_proxy")

_HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
])

_KERNEL_TO_RESOURCE: dict[str, str] = {}


def _eg_http_url() -> str:
    """Internal HTTP URL of Enterprise Gateway."""
    return eg_settings.internal_url()


def _eg_ws_url() -> str:
    return _eg_http_url().replace("http://", "ws://").replace("https://", "wss://")


def _kernel_catalog_api_url() -> str:
    """Return a notebook-kernel-safe catalog URL from the container/network perspective."""
    return try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"


async def _kernel_models() -> list[dict]:
    """Every kernel EG currently knows about."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.get(f"{_eg_http_url()}/api/kernels")
    if not resp.is_success:
        return []
    try:
        return resp.json() or []
    except Exception:
        return []


def register_kernel_resource(kernel_id: str, resource_id: str) -> None:
    """Track which compute resource owns which EG kernel."""
    _KERNEL_TO_RESOURCE[kernel_id] = resource_id


def _resource_id_of(kernel: dict) -> str | None:
    """The compute resource a kernel is running on, if it is one of ours.

    Kernels are launched with ``KERNEL_COMPASSX_JOB_ID`` set to the compute
    resource id (see ``start_kernel_for_resource``), which is the only link
    between a kernel and anything governable.
    """
    kernel_id = kernel.get("id")
    if kernel_id and kernel_id in _KERNEL_TO_RESOURCE:
        return _KERNEL_TO_RESOURCE[kernel_id]
    env = (kernel.get("metadata") or {}).get("env") or {}
    return env.get("KERNEL_COMPASSX_JOB_ID") or None


def _authorize_resource(guard: Guard, db, resource_id: str | None) -> None:
    """Require USE_COMPUTE on the resource a kernel belongs to.

    A kernel with no resource id was not started through CompassX, so there is
    nothing to check it against. It is refused rather than allowed: an
    unattributable kernel is the one case where failing open would hand over a
    shell on the cluster.
    """
    from app.compute.models.compute_resources import ComputeResource

    if not resource_id:
        raise HTTPException(status_code=404, detail="kernel not found")

    resource = (
        db.query(ComputeResource)
        .filter(
            ComputeResource.id == resource_id,
            ComputeResource.workspace_id == guard.workspace_id,
        )
        .first()
    )
    if resource is None:
        raise HTTPException(status_code=404, detail="kernel not found")

    if resource.is_default:
        return
    guard.require(Privilege.USE_COMPUTE, Securable.compute(resource_id))


async def _authorize_kernel(guard: Guard, db, kernel_id: str) -> None:
    """Require access to the compute resource behind ``kernel_id``."""
    resource_id = _KERNEL_TO_RESOURCE.get(kernel_id)
    if resource_id:
        _authorize_resource(guard, db, resource_id)
        return

    for kernel in await _kernel_models():
        if kernel.get("id") == kernel_id:
            res_id = _resource_id_of(kernel)
            if res_id:
                _authorize_resource(guard, db, res_id)
                return
            from app.compute.models.compute_resources import ComputeResource
            default_res = (
                db.query(ComputeResource)
                .filter(
                    ComputeResource.workspace_id == guard.workspace_id,
                    ComputeResource.is_default == True,
                )
                .first()
            )
            if default_res:
                _KERNEL_TO_RESOURCE[kernel_id] = default_res.id
                _authorize_resource(guard, db, default_res.id)
                return
    raise HTTPException(status_code=404, detail="kernel not found")


class _WSDenied(Exception):
    """A WebSocket that must be closed instead of accepted."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _ws_group_ids(user_id: str) -> tuple[str, ...]:
    from app.database import AccountSessionLocal
    from app.user_manager.models.account_models import UmGroupMember

    if AccountSessionLocal is None:
        return ()
    db = AccountSessionLocal()
    try:
        rows = (
            db.query(UmGroupMember.group_id)
            .filter(UmGroupMember.user_id == user_id)
            .all()
        )
        return tuple(str(row[0]) for row in rows)
    except Exception:
        logger.exception("Group expansion failed for principal %s", user_id)
        return ()
    finally:
        db.close()


def _ws_guard(websocket: WebSocket) -> tuple[Guard, object]:
    """Build a Guard for a WebSocket connection, or refuse it."""
    from app.database import SystemSessionLocal
    from app.governance.resolver import Principal, load_permission_set
    from app.workspace.middleware import (
        WorkspaceAuthError,
        extract_slug_from_path,
        resolve_workspace_context,
    )

    params = websocket.query_params
    slug = (
        extract_slug_from_path(websocket.url.path)
        or params.get("workspace")
        or websocket.headers.get("x-workspace-slug")
    )
    if not slug:
        raise _WSDenied(4401, "Missing workspace")

    try:
        ctx = resolve_workspace_context(slug, params.get("token"))
    except WorkspaceAuthError as exc:
        raise _WSDenied(4401 if exc.status_code == 401 else 4403, exc.message)

    if SystemSessionLocal is None:
        raise _WSDenied(4503, "system database not available")

    db = SystemSessionLocal()
    try:
        principal = Principal(
            id=str(ctx.principal_id),
            type="user",
            is_account_admin=ctx.is_account_admin,
            group_ids=_ws_group_ids(str(ctx.principal_id)),
            workspace_roles={str(ctx.workspace_id): ctx.principal_role},
        )
        workspace_id = str(ctx.workspace_id)
        guard = Guard(
            load_permission_set(db, principal, workspace_id),
            db,
            principal,
            workspace_id,
        )
    except Exception:
        db.close()
        raise
    return guard, db


async def _proxy(method: str, path: str, request: Request) -> Response:
    base = _eg_http_url()
    target_url = f"{base}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
    }
    body = await request.body()

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        upstream = await client.request(method, target_url, headers=forward_headers, content=body)

    response_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP
        and k.lower() not in ("content-encoding", "content-length")
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
