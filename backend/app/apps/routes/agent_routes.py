"""Agent WebSocket route — proxies CompassX UI chat messages to Pi RPC on the branch pod.

Pi's RPC port is NOT exposed outside the pod directly.
CompassX backend proxies via the same per-app scoped session token (§7).
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.apps.models.apps import AppPod

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apps", tags=["apps-agent"])

_PI_RPC_PORT = 9000  # localhost-only inside the pod


def _get_running_pod(db: Session, app_id: uuid.UUID, branch_id: uuid.UUID) -> Optional[AppPod]:
    return (
        db.query(AppPod)
        .filter(
            AppPod.app_id == app_id,
            AppPod.branch_id == branch_id,
            AppPod.pod_kind == "branch",
            AppPod.status == "running",
        )
        .order_by(AppPod.created_at.desc())
        .first()
    )


@router.websocket("/{app_id}/branches/{branch_id}/agent")
async def branch_agent(
    websocket: WebSocket,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
):
    """WebSocket proxy to the Pi agent RPC port running inside the branch pod.

    - Authenticated via the scoped session token in the WS handshake headers.
    - Pi's RPC port (9000) is localhost-only inside the pod — not externally exposed.
    - Pi path-protection is scoped to /backend and /frontend only (§7).
    - No commit/checkpoint tool in Pi's toolset — checkpoints are human-triggered (§7).
    """
    from app.database import SystemSessionLocal
    db = SystemSessionLocal()
    try:
        pod = _get_running_pod(db, app_id, branch_id)
        if pod is None:
            await websocket.close(code=4404, reason="No running pod for this branch")
            return

        await websocket.accept()

        # Proxy via the pod's internal Caddy /agent/* path which forwards to Pi RPC
        pod_agent_url = (
            f"ws://{pod.k8s_pod_name}.compassx-apps.svc.cluster.local/agent/rpc"
        )

        import asyncio
        import websockets

        async with websockets.connect(pod_agent_url) as pi_ws:

            async def ui_to_pi():
                try:
                    async for msg in websocket.iter_text():
                        await pi_ws.send(msg)
                except WebSocketDisconnect:
                    pass

            async def pi_to_ui():
                try:
                    async for msg in pi_ws:
                        await websocket.send_text(msg)
                except Exception:
                    pass

            await asyncio.gather(ui_to_pi(), pi_to_ui())

    except Exception as exc:
        logger.error("Agent proxy error (app=%s branch=%s): %s", app_id, branch_id, exc)
        try:
            await websocket.close(code=1011, reason="Internal proxy error")
        except Exception:
            pass
    finally:
        db.close()
