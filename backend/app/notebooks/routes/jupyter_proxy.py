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
"""
import asyncio
import logging

import httpx
import websockets
import websockets.exceptions
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from starlette.websockets import WebSocketState

from compassx.lookup import try_resolve_url_container
from services.enterprise_gateway.config import eg_settings
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notebook/jupyter", tags=["jupyter-proxy"])

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


# ── WebSocket proxy (must be registered BEFORE HTTP catch-all) ────────────────

@router.websocket("/api/kernels/{kernel_id}/channels")
async def proxy_kernel_ws(websocket: WebSocket, kernel_id: str) -> None:
    """Bridge browser WebSocket ↔ Enterprise Gateway kernel channel."""
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


@router.get("/api")
async def proxy_api_info(request: Request) -> Response:
    return await _proxy("GET", "api", request)


@router.get("/api/kernelspecs")
async def proxy_kernelspecs(request: Request) -> Response:
    return await _proxy("GET", "api/kernelspecs", request)


@router.get("/api/kernels")
async def proxy_kernels_list(request: Request) -> Response:
    return await _proxy("GET", "api/kernels", request)


@router.post("/api/kernels")
async def proxy_kernels_start(request: Request) -> Response:
    import json
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}

    auth_header = request.headers.get("Authorization", "")
    session_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

    if "env" not in payload:
        payload["env"] = {}

    catalog_api_url = _kernel_catalog_api_url()

    payload["env"].setdefault("KERNEL_NOTEBOOK_SESSION_TOKEN", session_token)
    payload["env"].setdefault("KERNEL_CATALOG_API_URL", catalog_api_url)
    payload["env"].setdefault("NOTEBOOK_SESSION_TOKEN", session_token)
    payload["env"].setdefault("CATALOG_API_URL", catalog_api_url)

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


@router.get("/api/kernels/{kernel_id}")
async def proxy_kernel_get(kernel_id: str, request: Request) -> Response:
    return await _proxy("GET", f"api/kernels/{kernel_id}", request)


@router.delete("/api/kernels/{kernel_id}")
async def proxy_kernel_delete(kernel_id: str, request: Request) -> Response:
    return await _proxy("DELETE", f"api/kernels/{kernel_id}", request)


@router.patch("/api/kernels/{kernel_id}")
async def proxy_kernel_restart(kernel_id: str, request: Request) -> Response:
    return await _proxy("PATCH", f"api/kernels/{kernel_id}", request)





