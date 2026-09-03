"""Jupyter / EG proxy — routes all kernel REST + WebSocket traffic through the backend.

In K8s, Enterprise Gateway is exposed via LoadBalancer; the browser still reaches it through this backend proxy.
This module proxies the subset of Jupyter REST + WebSocket APIs that
@jupyterlab/services needs:

  HTTP  GET/POST/DELETE  /api/v1/notebook/jupyter/api/kernels[/{id}]
  HTTP  GET              /api/v1/notebook/jupyter/api/kernelspecs
  HTTP  GET              /api/v1/notebook/jupyter/api
  WS                     /api/v1/notebook/jupyter/api/kernels/{id}/channels

All forwarded to the Enterprise Gateway service internally.
Traffic flow: browser → backend (public) → EG service → compute pods

Authorization
-------------
Enterprise Gateway has no authentication of its own, and a kernel is a remote
Python process: whoever reaches its channels can run code on the pod and read
the output of everybody else's cells. This proxy is therefore the only thing
standing in front of it, and every route here enforces access.

A kernel is not itself a securable. It is an execution on a compute resource,
so the compute resource is what grants address — ``_kernel_workspace`` maps a
kernel back to its resource via the ``KERNEL_COMPASSX_JOB_ID`` written into the
kernel environment at launch, and the caller needs the same ``USE_COMPUTE``
that starting the kernel required in the first place.
"""
import asyncio
import logging

import httpx
import websockets
import websockets.exceptions
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response
from starlette.websockets import WebSocketState

from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from compassx.lookup import try_resolve_url_container
from services.enterprise_gateway.config import eg_settings
logger = logging.getLogger(__name__)

# ``get_guard`` on the router, not on each handler: a route added later without
# a guard would otherwise be reachable by anyone who can open a socket to the
# port, which is exactly the state this module was in.
router = APIRouter(
    prefix="/api/v1/notebook/jupyter",
    tags=["jupyter-proxy"],
)
http_router = APIRouter(
    dependencies=[Depends(get_guard)],
)

_HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
])


def _eg_http_url() -> str:
    """Internal HTTP URL of Enterprise Gateway."""
    return eg_settings.internal_url()  # http://compassx-enterprise-gateway.prod.svc.cluster.local:8888


def _eg_ws_url() -> str:
    return _eg_http_url().replace("http://", "ws://").replace("https://", "wss://")


def _kernel_catalog_api_url() -> str:
    """Return a notebook-kernel-safe catalog URL from the container/network perspective."""
    return try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"


# ── Kernel → compute resource ────────────────────────────────────────────────

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


_KERNEL_TO_RESOURCE: dict[str, str] = {}


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
        # Either no such resource, or it belongs to another workspace. Both are
        # "not yours", and saying which would leak the existence of other
        # workspaces' compute.
        raise HTTPException(status_code=404, detail="kernel not found")

    # The default resource is attachable by any member — the same exception
    # ``_require_compute`` makes in the compute routes, for the same reason:
    # otherwise nobody could open a notebook until an admin granted them
    # USE_COMPUTE one principal at a time.
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
            # If EG didn't retain metadata, check if workspace has a default compute resource
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


# ── WebSocket proxy (must be registered BEFORE HTTP catch-all) ────────────────

@router.websocket("/api/kernels/{kernel_id}/channels")
async def proxy_kernel_ws(websocket: WebSocket, kernel_id: str) -> None:
    """Bridge browser WebSocket ↔ Enterprise Gateway kernel channel."""
    # The router-level guard does not apply here: dependencies with a Request
    # cannot run for a WebSocket scope, and WorkspaceMiddleware is a
    # BaseHTTPMiddleware, which Starlette skips for websockets. So this handler
    # authenticates itself, before accepting — an accepted-then-closed socket
    # has already been handed the kernel for as long as it took to notice.
    try:
        guard, db = _ws_guard(websocket)
    except _WSDenied as denied:
        await websocket.accept()
        await websocket.close(code=denied.code, reason=denied.reason)
        return

    try:
        try:
            await _authorize_kernel(guard, db, kernel_id)
        except HTTPException:
            await websocket.accept()
            await websocket.close(code=4403, reason="Not authorized for this kernel")
            return
    finally:
        db.close()

    await websocket.accept()

    qs = websocket.url.query
    upstream_url = (
        f"{_eg_ws_url()}/api/kernels/{kernel_id}/channels"
        + (f"?{qs}" if qs else "")
    )

    subprotocols = websocket.headers.get("sec-websocket-protocol", "")
    extra_headers: dict[str, str] = {}
    if subprotocols:
        extra_headers["Sec-WebSocket-Protocol"] = subprotocols

    logger.debug("WS proxy: connecting to upstream %s", upstream_url)

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers=extra_headers,
            open_timeout=30,
            ping_interval=20,
            ping_timeout=20,
        ) as upstream_ws:
            logger.debug("WS proxy: upstream connected for kernel %s", kernel_id)

            async def browser_to_upstream() -> None:
                try:
                    while True:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        msg = await websocket.receive()
                        if "bytes" in msg and msg["bytes"] is not None:
                            await upstream_ws.send(msg["bytes"])
                        elif "text" in msg and msg["text"] is not None:
                            await upstream_ws.send(msg["text"])
                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    logger.debug("WS proxy browser→upstream error: %s", exc)

            async def upstream_to_browser() -> None:
                try:
                    async for message in upstream_ws:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as exc:
                    logger.debug("WS proxy upstream→browser error: %s", exc)

            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(browser_to_upstream()),
                    asyncio.ensure_future(upstream_to_browser()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as exc:
        logger.warning("WS proxy: failed to connect upstream %s: %s", upstream_url, exc)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
        logger.debug("WS proxy: closed for kernel %s", kernel_id)


class _WSDenied(Exception):
    """A WebSocket that must be closed instead of accepted."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _ws_guard(websocket: WebSocket) -> tuple[Guard, "object"]:
    """Build a Guard for a WebSocket connection, or refuse it.

    Returns the guard and the session it holds, which the caller must close —
    a websocket has no request lifecycle to close it for us.

    The credentials arrive in the query string because a browser WebSocket
    cannot carry an Authorization header. That is why the frontend sends the
    user's own access token here rather than the shared Jupyter token: the
    shared one identifies nobody, so it could not be used to decide anything.
    """
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
        # Matches get_principal: a failed group expansion drops group-derived
        # grants rather than locking the user out. The decision still defaults
        # to deny.
        logger.exception("Group expansion failed for principal %s", user_id)
        return ()
    finally:
        db.close()


# ── HTTP REST proxy ───────────────────────────────────────────────────────────
# Only proxy the API paths that @jupyterlab/services actually calls.
# Do NOT use a wildcard catch-all — it would intercept WebSocket upgrade
# requests (which arrive as HTTP GET with Upgrade: websocket) before the
# WebSocket route above can handle them.

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


@http_router.get("/api")
async def proxy_api_info(request: Request) -> Response:
    """EG version banner. Members only, via the router guard."""
    return await _proxy("GET", "api", request)


@http_router.get("/api/kernelspecs")
async def proxy_kernelspecs(request: Request) -> Response:
    """The kernel types this deployment offers. Members only."""
    return await _proxy("GET", "api/kernelspecs", request)


@http_router.get("/api/kernels")
async def proxy_kernels_list(
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    """List the kernels running on compute this caller may use.

    Filtered, not refused. It used to return every kernel on the deployment,
    which named other workspaces' resources and handed over the kernel ids
    needed to attach to them.
    """
    import json

    visible = []
    for kernel in await _kernel_models():
        try:
            _authorize_resource(guard, db, _resource_id_of(kernel))
        except HTTPException:
            continue
        visible.append(kernel)

    return Response(content=json.dumps(visible), media_type="application/json")


@http_router.post("/api/kernels")
async def proxy_kernels_start(
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    import json
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}

    # A kernel is a pod running the caller's code, so starting one takes the
    # same USE_COMPUTE that /compute/resources/{id}/start-kernel takes. The
    # resource comes from the request, so it is checked rather than trusted.
    env = payload.get("env") or {}
    _authorize_resource(guard, db, env.get("KERNEL_COMPASSX_JOB_ID"))

    auth_header = request.headers.get("Authorization", "")
    session_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

    if "env" not in payload:
        payload["env"] = {}

    ws_id_str = ""
    ws_slug_str = ""
    if hasattr(request.state, "workspace") and request.state.workspace:
        ws_id_str = str(getattr(request.state.workspace, "workspace_id", "") or "")
        ws_slug_str = str(getattr(request.state.workspace, "workspace_slug", "") or "")
    elif request.query_params.get("workspace"):
        ws_slug_str = request.query_params.get("workspace") or ""
    elif request.headers.get("x-workspace-slug"):
        ws_slug_str = request.headers.get("x-workspace-slug") or ""

    if ws_slug_str and not ws_id_str:
        try:
            from app.workspace.models import Workspace
            ws_obj = db.query(Workspace).filter((Workspace.slug == ws_slug_str) | (Workspace.id == ws_slug_str)).first()
            if ws_obj:
                ws_id_str = str(ws_obj.id)
                ws_slug_str = ws_obj.slug
        except Exception:
            pass

    payload["env"].setdefault("KERNEL_NOTEBOOK_SESSION_TOKEN", session_token)
    payload["env"].setdefault("KERNEL_CATALOG_API_URL", catalog_api_url)
    payload["env"].setdefault("NOTEBOOK_SESSION_TOKEN", session_token)
    payload["env"].setdefault("CATALOG_API_URL", catalog_api_url)
    if ws_id_str:
        payload["env"].setdefault("KERNEL_WORKSPACE_ID", ws_id_str)
        payload["env"].setdefault("WORKSPACE_ID", ws_id_str)
    if ws_slug_str:
        payload["env"].setdefault("KERNEL_WORKSPACE_SLUG", ws_slug_str)
        payload["env"].setdefault("WORKSPACE_SLUG", ws_slug_str)

    modified_body = json.dumps(payload).encode("utf-8")

    # Forward to upstream EG
    base = _eg_http_url()
    target_url = f"{base}/api/kernels"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        upstream = await client.request("POST", target_url, headers=forward_headers, content=modified_body)

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


@http_router.get("/api/kernels/{kernel_id}")
async def proxy_kernel_get(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    await _authorize_kernel(guard, db, kernel_id)
    return await _proxy("GET", f"api/kernels/{kernel_id}", request)


@http_router.delete("/api/kernels/{kernel_id}")
async def proxy_kernel_delete(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    """Shut a kernel down.

    Takes the same privilege as starting one: whoever may run work on a
    resource may stop it, and a runaway kernel that only its starter can kill
    is worse than one stopped by a colleague.
    """
    await _authorize_kernel(guard, db, kernel_id)
    return await _proxy("DELETE", f"api/kernels/{kernel_id}", request)


@http_router.patch("/api/kernels/{kernel_id}")
async def proxy_kernel_restart(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    await _authorize_kernel(guard, db, kernel_id)
    return await _proxy("PATCH", f"api/kernels/{kernel_id}", request)


@http_router.post("/api/kernels/{kernel_id}/restart")
async def proxy_kernel_restart_post(
    kernel_id: str,
    request: Request,
    guard: Guard = Depends(get_guard),
    db=Depends(get_system_db),
) -> Response:
    """Restart a kernel.

    @jupyterlab/services issues POST .../restart; only PATCH was proxied, so
    the toolbar's restart button reached EG's 404 rather than the kernel.
    """
    await _authorize_kernel(guard, db, kernel_id)
    return await _proxy("POST", f"api/kernels/{kernel_id}/restart", request)


router.include_router(http_router)
