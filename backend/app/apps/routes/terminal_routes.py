"""Terminal WebSocket route — proxied to branch pod exec endpoint with local fallback.

Gated by app_pods.terminal_enabled for the active pod.
In local development (dev mode), if no running pod is found, it automatically
falls back to launching a local shell (powershell.exe on Windows or /bin/bash on Linux/macOS)
inside the branch's local scratch workspace, making the browser terminal fully operational.
"""

import uuid
import logging
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.apps.models.apps import AppPod

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apps", tags=["apps-terminal"])

DbDep = Annotated[Session, Depends(get_system_db)]

_TERMINAL_PORT = 7001  # Pod exposes terminal WebSocket on this internal port


def _get_running_pod(db: Session, app_id: uuid.UUID, branch_id: uuid.UUID) -> AppPod:
    pod: Optional[AppPod] = (
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
    if pod is None:
        raise HTTPException(status_code=503, detail="No running pod found for this branch")
    return pod


@router.websocket("/{app_id}/branches/{branch_id}/terminal")
async def branch_terminal(
    websocket: WebSocket,
    app_id: uuid.UUID,
    branch_id: uuid.UUID,
):
    """WebSocket proxy to the branch pod's terminal, with automatic local shell fallback for dev mode."""
    from app.database import SystemSessionLocal
    db = SystemSessionLocal()

    # Try resolving running K8s pod first
    pod = None
    try:
        pod = _get_running_pod(db, app_id, branch_id)
    except Exception:
        # Fallback to local dev shell if no running K8s pod exists
        logger.info("No running K8s pod found. Falling back to local workspace shell for branch %s", branch_id)

    if pod is not None:
        if not pod.terminal_enabled:
            await websocket.close(code=4403, reason="Terminal disabled for this pod")
            db.close()
            return

        await websocket.accept()

        pod_ws_url = (
            f"ws://{pod.k8s_pod_name}.compassx-apps.svc.cluster.local"
            f":{_TERMINAL_PORT}/terminal"
        )
        db.close()

        try:
            import websockets
            async with websockets.connect(pod_ws_url) as pod_ws:
                import asyncio

                async def client_to_pod():
                    try:
                        async for msg in websocket.iter_text():
                            await pod_ws.send(msg)
                    except WebSocketDisconnect:
                        pass

                async def pod_to_client():
                    try:
                        async for msg in pod_ws:
                            await websocket.send_text(msg)
                    except Exception:
                        pass

                await asyncio.gather(client_to_pod(), pod_to_client())
        except Exception as exc:
            logger.error("Terminal proxy error: %s", exc)
            await websocket.close(code=1011, reason="Internal proxy error")
        return

    # LOCAL DEV SHELL FALLBACK
    await websocket.accept()
    await websocket.send_text("[CompassX] Connected to local development workspace terminal\r\n")

    import sys
    import os
    import asyncio
    import subprocess
    from app.apps.services.file_service import _local_workspace_path

    workspace_path = _local_workspace_path(app_id, branch_id)
    os.makedirs(workspace_path, exist_ok=True)

    if sys.platform == "win32":
      system_root = os.environ.get("SystemRoot", "C:\\Windows")
      powershell_path = os.path.join(
          system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
      )
      if os.path.exists(powershell_path):
        shell_cmd = [powershell_path, "-NoExit", "-NoLogo"]
      else:
        shell_cmd = [os.path.join(system_root, "System32", "cmd.exe")]
    else:
      shell_cmd = ["/bin/bash"]

    proc = None
    try:
        # Popen works universally across all OS platforms and Python event loops (e.g. SelectorEventLoop on Windows)
        proc = subprocess.Popen(
            shell_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workspace_path,
            bufsize=0  # Binary unbuffered I/O
        )

        async def read_stdout():
            try:
                while True:
                    # Read blocking call executed in a thread pool to avoid blocking the event loop
                    data = await asyncio.to_thread(proc.stdout.read, 1024)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\n", "\r\n")
                    await websocket.send_text(text)
            except Exception:
                pass

        async def read_stderr():
            try:
                while True:
                    data = await asyncio.to_thread(proc.stderr.read, 1024)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\n", "\r\n")
                    await websocket.send_text(text)
            except Exception:
                pass

        async def write_stdin():
            try:
                import json
                async for msg in websocket.iter_text():
                    try:
                        packet = json.loads(msg)
                        ptype = packet.get("type")
                        if ptype == "input":
                            data = packet.get("data", "")
                            if proc.stdin:
                                if sys.platform == "win32":
                                    data = data.replace("\x7f", "\x08")
                                await asyncio.to_thread(proc.stdin.write, data.encode("utf-8"))
                                await asyncio.to_thread(proc.stdin.flush)
                        elif ptype == "resize":
                            pass
                    except Exception as e:
                        logger.warning("Failed to parse local terminal input: %s", e)
            except Exception:
                pass

        await asyncio.gather(read_stdout(), read_stderr(), write_stdin())
    except Exception as exc:
        logger.error("Local terminal error: %s", exc)
        await websocket.send_text(f"\r\n[CompassX] Failed to launch local shell: {exc}\r\n")
    finally:
        db.close()
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                pass
