import asyncio
import logging

import websockets
import websockets.exceptions
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.notebooks.kernel.registry import (
    _KERNEL_TO_RESOURCE,
    _WSDenied,
    _authorize_kernel,
    _eg_ws_url,
    _ws_guard,
)

logger = logging.getLogger("app.notebooks.routes.jupyter_proxy")


class ProxyKernelWs:
    async def execute(self, websocket: WebSocket, kernel_id: str) -> None:
        from app.platform_mode import ensure_deployed

        try:
            ensure_deployed("enterprise-gateway")
        except HTTPException as exc:
            await websocket.accept()
            await websocket.close(code=1008, reason=str(exc.detail)[:120])
            return

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
                            # Reset idle timer for active compute resource
                            res_id = _KERNEL_TO_RESOURCE.get(kernel_id)
                            if res_id:
                                try:
                                    from app.services.sandbox_reaper_service import sandbox_reaper_service
                                    sandbox_reaper_service.touch_compute_activity(res_id)
                                except Exception:
                                    pass

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


def proxy_kernel_ws(websocket, kernel_id):
    return ProxyKernelWs().execute(websocket, kernel_id)
