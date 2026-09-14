"""Dev Terminal Service — Real-time interactive WebSocket terminal and command exec for Dev Sandboxes (SOLID / SRP)."""
import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.models.app import App
from app.services.drivers.factory import driver_factory

logger = logging.getLogger(__name__)


class DevTerminalService:
    """Orchestrates interactive container/pod PTY sessions and command execution."""

    def _resolve_workspace_folder(self, app: App, workspace_id: Optional[str] = None, workspace_name: Optional[str] = None) -> str:
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        ws_name = "default"
        if workspace_name:
            ws_name = re.sub(r"[^a-zA-Z0-9_-]", "-", workspace_name.strip()).strip("-").lower() or "default"
        elif workspace_id:
            try:
                from app.database import SystemSessionLocal
                from app.models.dev_workspace import DevWorkspace
                with SystemSessionLocal() as db:
                    ws = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                    ).first()
                    if ws and ws.name:
                        ws_name = ws.name
            except Exception:
                ws_name = workspace_id
        return f"{clean_id}/{ws_name}"

    def exec_command(
        self,
        app: App,
        command: str,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a single non-interactive shell command in the active dev pod/container."""
        driver = driver_factory.get_dev_driver()
        ws_folder = self._resolve_workspace_folder(app, workspace_id=workspace_id, workspace_name=workspace_name)
        return driver.exec_command_in_dev(app, command=command, workspace_folder=ws_folder)

    async def handle_terminal_websocket(
        self,
        websocket: WebSocket,
        app: App,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
        cols: int = 100,
        rows: int = 30,
    ) -> None:
        """Bridge browser WebSocket with the live interactive PTY terminal inside the dev pod/container."""
        await websocket.accept()

        driver = driver_factory.get_dev_driver()
        ws_folder = self._resolve_workspace_folder(app, workspace_id=workspace_id, workspace_name=workspace_name)
        leaf_ws = ws_folder.split("/")[-1]

        # Send greeting banner
        welcome_banner = (
            f"\r\n\x1b[1;35m╭──────────────────────────────────────────────────────────╮\x1b[0m\r\n"
            f"\x1b[1;35m│\x1b[0m \x1b[1;32m● Connected to Dev Sandbox Terminal\x1b[0m                      \x1b[1;35m│\x1b[0m\r\n"
            f"\x1b[1;35m│\x1b[0m App: \x1b[1;36m{app.name[:25]:<25}\x1b[0m Workspace: \x1b[1;33m{leaf_ws[:15]:<15}\x1b[0m \x1b[1;35m│\x1b[0m\r\n"
            f"\x1b[1;35m│\x1b[0m Path: \x1b[90m/workspaces/{ws_folder[:38]:<38}\x1b[0m \x1b[1;35m│\x1b[0m\r\n"
            f"\x1b[1;35m╰──────────────────────────────────────────────────────────╯\x1b[0m\r\n\r\n"
        )
        try:
            await websocket.send_text(welcome_banner)
        except Exception:
            return

        client_stream = driver.open_terminal_ws_client(app, workspace_folder=ws_folder, cols=cols, rows=rows)
        if not client_stream:
            err_msg = "\r\n\x1b[1;31m[ERROR] Failed to attach interactive terminal. Is the Dev Pod running?\x1b[0m\r\n"
            try:
                await websocket.send_text(err_msg)
                await websocket.close(code=1011, reason="Dev container not reachable")
            except Exception:
                pass
            return

        # Check if Kubernetes WSClient
        is_k8s_ws = hasattr(client_stream, "write_stdin") and hasattr(client_stream, "read_stdout")

        if is_k8s_ws:
            await self._pump_k8s_terminal(websocket, client_stream)
        else:
            # Subprocess (Docker / Local)
            await self._pump_subprocess_terminal(websocket, client_stream)

    async def _pump_k8s_terminal(self, websocket: WebSocket, k8s_client: Any) -> None:
        """Handle bidirectional pump for Kubernetes WSClient."""
        from kubernetes.stream.ws_client import RESIZE_CHANNEL

        stop_event = asyncio.Event()

        async def pod_to_browser():
            loop = asyncio.get_running_loop()
            try:
                while not stop_event.is_set():
                    if websocket.client_state != WebSocketState.CONNECTED or not k8s_client.is_open():
                        break
                    # Non-blocking or short timeout read in executor
                    chunk = await loop.run_in_executor(None, k8s_client.read_stdout, 0.05)
                    if chunk:
                        await websocket.send_text(chunk)
                    else:
                        # Also check stderr
                        err_chunk = await loop.run_in_executor(None, k8s_client.read_stderr, 0.02)
                        if err_chunk:
                            await websocket.send_text(err_chunk)
                        else:
                            await asyncio.sleep(0.02)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.debug("Pod to browser pipe ended: %s", e)
            finally:
                stop_event.set()

        async def browser_to_pod():
            try:
                while not stop_event.is_set():
                    if websocket.client_state != WebSocketState.CONNECTED or not k8s_client.is_open():
                        break
                    raw = await websocket.receive_text()
                    if not raw:
                        continue

                    # Handle control JSON (resize / ping)
                    if raw.startswith('{"type":') or raw.startswith('{"cols":'):
                        try:
                            data = json.loads(raw)
                            msg_type = data.get("type")
                            if msg_type == "resize" or ("cols" in data and "rows" in data):
                                c = int(data.get("cols", 80))
                                r = int(data.get("rows", 24))
                                k8s_client.write_channel(RESIZE_CHANNEL, json.dumps({"Width": c, "Height": r}))
                                continue
                            elif msg_type == "ping":
                                await websocket.send_text(json.dumps({"type": "pong"}))
                                continue
                        except Exception:
                            pass

                    # Normal stdin keystroke / text
                    k8s_client.write_stdin(raw)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.debug("Browser to pod pipe ended: %s", e)
            finally:
                stop_event.set()

        try:
            await asyncio.gather(pod_to_browser(), browser_to_pod(), return_exceptions=True)
        finally:
            try:
                k8s_client.close()
            except Exception:
                pass
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close()
                except Exception:
                    pass

    async def _pump_subprocess_terminal(self, websocket: WebSocket, proc: Any) -> None:
        """Handle bidirectional pump for Docker / local subprocess."""
        stop_event = asyncio.Event()

        async def proc_to_browser():
            loop = asyncio.get_running_loop()
            try:
                while not stop_event.is_set() and proc.poll() is None:
                    if websocket.client_state != WebSocketState.CONNECTED:
                        break
                    # Read bytes
                    data = await loop.run_in_executor(None, proc.stdout.read1, 1024)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        await websocket.send_text(text)
                    else:
                        await asyncio.sleep(0.02)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.debug("Subprocess stdout pipe ended: %s", e)
            finally:
                stop_event.set()

        async def browser_to_proc():
            try:
                while not stop_event.is_set() and proc.poll() is None:
                    if websocket.client_state != WebSocketState.CONNECTED:
                        break
                    raw = await websocket.receive_text()
                    if not raw:
                        continue

                    # Check control messages
                    if raw.startswith('{"type":') or raw.startswith('{"cols":'):
                        try:
                            data = json.loads(raw)
                            if data.get("type") == "ping":
                                await websocket.send_text(json.dumps({"type": "pong"}))
                                continue
                        except Exception:
                            pass

                    # Write to stdin
                    if proc.stdin and not proc.stdin.closed:
                        proc.stdin.write(raw.encode("utf-8"))
                        proc.stdin.flush()
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.debug("Browser to subprocess stdin pipe ended: %s", e)
            finally:
                stop_event.set()

        try:
            await asyncio.gather(proc_to_browser(), browser_to_proc(), return_exceptions=True)
        finally:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close()
                except Exception:
                    pass


dev_terminal_service = DevTerminalService()
