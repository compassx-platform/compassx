"""Centralized Sandbox Orchestration Service.

Provides a unified lifecycle and execution API for all consumer modules
(App Service, Omnigent / Agent runtime, Notebook Kernels, Jobs Runner).
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.sandbox.drivers.factory import sandbox_driver_factory
from app.sandbox.interfaces import BaseSandboxDriver, SandboxHandle
from app.sandbox.models import (
    ExecResult,
    InitScript,
    SandboxInstance,
    SandboxProgress,
    SandboxSpec,
    SandboxStatus,
)

logger = logging.getLogger(__name__)


def _normalize_key(val: Optional[str]) -> str:
    if not val:
        return ""
    return str(val).strip().lower().replace("_", "-")


class SandboxService:
    """Centralized management service for isolated compute sandboxes across platform profiles."""

    def __init__(self):
        self._instances: Dict[str, SandboxInstance] = {}

    def _get_driver_for_mode(self, mode: Optional[str] = None) -> BaseSandboxDriver:
        return sandbox_driver_factory.get_driver(mode)

    def find_active_sandbox(
        self,
        sandbox_id: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_module: Optional[str] = None,
    ) -> Optional[SandboxInstance]:
        """Find an existing sandbox matching ID or consumer key (exact or normalized)."""
        norm_sb_id = _normalize_key(sandbox_id)
        norm_c_key = _normalize_key(consumer_key)

        # 1. Check in-memory instances
        for sb in self._instances.values():
            if norm_sb_id and (
                _normalize_key(sb.id) == norm_sb_id
                or _normalize_key(sb.labels.get("compassx.sandbox-id") if sb.labels else None) == norm_sb_id
            ):
                return sb
            if norm_c_key:
                if _normalize_key(sb.consumer_key) == norm_c_key:
                    return sb
                if sb.labels and (
                    _normalize_key(sb.labels.get("compassx.consumer_key")) == norm_c_key
                    or _normalize_key(sb.labels.get("compassx.consumer-key")) == norm_c_key
                ):
                    return sb
                if sb.metadata and _normalize_key(sb.metadata.get("app_id")) == norm_c_key:
                    return sb

        # 2. Check discovered infrastructure instances
        try:
            discovered = self.list_sandboxes(consumer_module=consumer_module)
            for sb in discovered:
                matched = False
                if norm_sb_id and (
                    _normalize_key(sb.id) == norm_sb_id
                    or _normalize_key(sb.labels.get("compassx.sandbox-id") if sb.labels else None) == norm_sb_id
                ):
                    matched = True
                elif norm_c_key:
                    if _normalize_key(sb.consumer_key) == norm_c_key:
                        matched = True
                    elif sb.labels and (
                        _normalize_key(sb.labels.get("compassx.consumer_key")) == norm_c_key
                        or _normalize_key(sb.labels.get("compassx.consumer-key")) == norm_c_key
                    ):
                        matched = True
                    elif sb.metadata and _normalize_key(sb.metadata.get("app_id")) == norm_c_key:
                        matched = True

                if matched:
                    target_id = sandbox_id or sb.id
                    sb.id = target_id
                    self._instances[target_id] = sb
                    return sb
        except Exception as exc:
            logger.debug("Error during sandbox lookup: %s", exc)

        return None

    def ensure_sandbox(self, spec: SandboxSpec) -> SandboxInstance:
        """Idempotently ensure a sandbox is running for the given spec.

        If already running, immediately returns existing details.
        If suspended, resumes compute and returns.
        If not present or failed, provisions fresh compute and executes init scripts with step-by-step progress tracking.
        """
        start_time = time.time()
        c_key = spec.consumer_key or spec.sandbox_id

        # 1. Check for existing sandbox
        existing = self.find_active_sandbox(
            sandbox_id=spec.sandbox_id,
            consumer_key=c_key,
            consumer_module=spec.consumer_module,
        )

        if existing:
            driver = self._get_driver_for_mode(existing.runtime_mode)
            live_status = driver.get_status(existing)
            existing.status = live_status
            existing.endpoints = driver.get_endpoints(existing)

            # A. Already active & running
            if live_status in (SandboxStatus.READY, SandboxStatus.RUNNING):
                existing.progress = SandboxProgress(
                    stage="ready",
                    step_index=len(spec.init_scripts) + 2,
                    total_steps=len(spec.init_scripts) + 2,
                    step_name="Ready",
                    message="Sandbox is active and ready",
                    percent=100,
                    elapsed_seconds=0.0,
                )
                logger.info("ensure_sandbox: Returning existing active sandbox %s (%s)", existing.name, existing.id)
                return existing

            # B. Suspended -> Resume
            if live_status in (SandboxStatus.SUSPENDED, SandboxStatus.STOPPED):
                existing.progress = SandboxProgress(
                    stage="starting",
                    step_index=1,
                    total_steps=2,
                    step_name="Resume Compute",
                    message="Resuming suspended sandbox compute...",
                    percent=50,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                self.resume_sandbox(existing.id)
                existing.endpoints = driver.get_endpoints(existing)
                existing.progress = SandboxProgress(
                    stage="ready",
                    step_index=2,
                    total_steps=2,
                    step_name="Ready",
                    message="Sandbox resumed successfully",
                    percent=100,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )
                return existing

            # C. In-progress provisioning
            if live_status in (SandboxStatus.PROVISIONING, SandboxStatus.INITIALIZING):
                return existing

        # 2. Fresh Provisioning & Step-by-Step Execution
        total_steps = 2 + len(spec.init_scripts)  # 1: Allocate, 2: Start, 3..N: Init scripts

        # Inject consumer_key into labels if present
        if spec.consumer_key and "compassx.consumer_key" not in spec.labels:
            spec.labels["compassx.consumer_key"] = spec.consumer_key

        driver = self._get_driver_for_mode(spec.runtime_mode)

        # Stage 1: Allocate Compute
        initial_progress = SandboxProgress(
            stage="allocating",
            step_index=1,
            total_steps=total_steps,
            step_name="Allocate Compute",
            message=f"Allocating compute sandbox for '{spec.name}'...",
            percent=10,
            elapsed_seconds=round(time.time() - start_time, 2),
        )

        instance = driver.provision(spec)
        instance.consumer_key = spec.consumer_key
        instance.status = SandboxStatus.PROVISIONING
        instance.progress = initial_progress
        self._instances[instance.id] = instance

        # Stage 2: Start Container Runtime
        instance.progress = SandboxProgress(
            stage="starting",
            step_index=2,
            total_steps=total_steps,
            step_name="Start Runtime",
            message="Starting sandbox container environment...",
            percent=25,
            elapsed_seconds=round(time.time() - start_time, 2),
        )

        # Stage 3: Sequential Init Scripts
        if spec.init_scripts:
            instance.status = SandboxStatus.INITIALIZING
            for idx, script in enumerate(spec.init_scripts):
                step_num = 3 + idx
                pct = int(25 + ((idx) / max(1, len(spec.init_scripts))) * 70)
                instance.progress = SandboxProgress(
                    stage="initializing",
                    step_index=step_num,
                    total_steps=total_steps,
                    step_name=script.name,
                    message=f"Running step [{idx + 1}/{len(spec.init_scripts)}]: {script.name}...",
                    percent=pct,
                    elapsed_seconds=round(time.time() - start_time, 2),
                )

                res = driver.exec_command(
                    instance,
                    command=script.command,
                    working_dir=script.working_dir or instance.working_dir,
                    env=script.env,
                    timeout=script.timeout_seconds,
                )

                if not res.success and not script.ignore_failure:
                    err_msg = f"Init step '{script.name}' failed with exit code {res.exit_code}: {res.stderr or res.stdout}"
                    logger.error(err_msg)
                    instance.status = SandboxStatus.FAILED
                    instance.error_message = err_msg
                    instance.progress = SandboxProgress(
                        stage="failed",
                        step_index=step_num,
                        total_steps=total_steps,
                        step_name=script.name,
                        message=err_msg,
                        percent=pct,
                        elapsed_seconds=round(time.time() - start_time, 2),
                        details={"exit_code": res.exit_code, "stderr": res.stderr, "stdout": res.stdout},
                    )
                    return instance

        # Check actual status from driver
        if instance.status == SandboxStatus.FAILED:
            instance.progress = SandboxProgress(
                stage="failed",
                step_index=total_steps,
                total_steps=total_steps,
                step_name="Failed",
                message=instance.error_message or "Sandbox startup failed",
                percent=100,
                elapsed_seconds=round(time.time() - start_time, 2),
                details={"error": instance.error_message},
            )
            logger.error("Sandbox '%s' (%s) FAILED in %.2fs: %s", instance.name, instance.id, time.time() - start_time, instance.error_message)
            return instance

        if instance.status == SandboxStatus.PROVISIONING:
            instance.progress = SandboxProgress(
                stage="starting",
                step_index=2,
                total_steps=total_steps,
                step_name="Provisioning",
                message="Sandbox compute is provisioning in cluster...",
                percent=50,
                elapsed_seconds=round(time.time() - start_time, 2),
            )
            return instance

        # Stage 4: Ready
        instance.status = SandboxStatus.READY
        instance.endpoints = driver.get_endpoints(instance)
        instance.progress = SandboxProgress(
            stage="ready",
            step_index=total_steps,
            total_steps=total_steps,
            step_name="Ready",
            message="Sandbox environment is ready",
            percent=100,
            elapsed_seconds=round(time.time() - start_time, 2),
        )
        logger.info("Sandbox '%s' (%s) is READY in %.2fs", instance.name, instance.id, time.time() - start_time)
        return instance

    def provision_sandbox(self, spec: SandboxSpec) -> SandboxHandle:
        """Provision a new compute sandbox and return a SandboxHandle."""
        instance = self.ensure_sandbox(spec)
        driver = self._get_driver_for_mode(instance.runtime_mode)
        return SandboxHandle(instance, driver, self)

    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInstance]:
        """Fetch sandbox instance by ID, refreshing its live status."""
        instance = self._instances.get(sandbox_id)
        if not instance:
            all_discovered = self.list_sandboxes()
            for disc in all_discovered:
                if disc.id == sandbox_id:
                    self._instances[sandbox_id] = disc
                    instance = disc
                    break

        if instance:
            driver = self._get_driver_for_mode(instance.runtime_mode)
            instance.status = driver.get_status(instance)
            instance.endpoints = driver.get_endpoints(instance)

        return instance

    def get_handle(self, sandbox_id: str) -> Optional[SandboxHandle]:
        """Get an executable handle for a running sandbox."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            return None
        driver = self._get_driver_for_mode(instance.runtime_mode)
        return SandboxHandle(instance, driver, self)

    def list_sandboxes(
        self,
        workspace_id: Optional[str] = None,
        consumer_module: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SandboxInstance]:
        """List all currently known and discovered sandboxes across drivers."""
        combined: Dict[str, SandboxInstance] = dict(self._instances)

        def _find_matching_key(item_id: str, c_key: Optional[str] = None) -> Optional[str]:
            norm_item = _normalize_key(item_id)
            norm_c = _normalize_key(c_key) if c_key else None
            for k, existing in list(combined.items()):
                if _normalize_key(k) == norm_item or _normalize_key(existing.id) == norm_item:
                    return k
                if norm_c and (
                    _normalize_key(existing.consumer_key) == norm_c
                    or _normalize_key(existing.labels.get("compassx.consumer-key") if existing.labels else None) == norm_c
                    or _normalize_key(existing.labels.get("compassx.consumer_key") if existing.labels else None) == norm_c
                    or _normalize_key(existing.metadata.get("app_id") if existing.metadata else None) == norm_c
                ):
                    return k
            return None

        # 1. Discover active sandboxes from driver
        driver = self._get_driver_for_mode()
        try:
            discovered = driver.discover_active_instances()
            for item in discovered:
                matched_key = _find_matching_key(item.id, item.consumer_key)
                if not matched_key:
                    combined[item.id] = item
                else:
                    existing_entry = combined[matched_key]
                    existing_entry.status = item.status
                    if item.endpoints:
                        existing_entry.endpoints = item.endpoints
                    if item.pod_name:
                        existing_entry.pod_name = item.pod_name
                    if item.image:
                        existing_entry.image = item.image
        except Exception as exc:
            logger.debug("Sandbox driver discovery error: %s", exc)

        # 2. Discover active Dev Sandboxes from Omnigent / Dev Studio
        try:
            from app.database import SystemSessionLocal
            from app.models.dev_workspace import DevWorkspace
            from app.models.app import App

            with SystemSessionLocal() as db:
                dev_workspaces = db.query(DevWorkspace).filter(DevWorkspace.status == "active").all()
                for ws in dev_workspaces:
                    app = db.query(App).filter(App.id == ws.app_id).first()
                    dev_sb_id = f"dev-app-{ws.app_id}"
                    c_key = f"app_{ws.app_id}"
                    matched_key = _find_matching_key(dev_sb_id, c_key)
                    if not matched_key:
                        app_name = app.name if app else ws.app_id
                        combined[dev_sb_id] = SandboxInstance(
                            id=dev_sb_id,
                            consumer_key=c_key,
                            name=f"{app_name} (Dev Sandbox)",
                            consumer_module="app",
                            workspace_id=app.workspace_id if app else None,
                            status=SandboxStatus.RUNNING,
                            runtime_mode=driver.__class__.__name__.replace("SandboxDriver", "").lower(),
                            image="compassx-dev-host:latest",
                            created_at=ws.created_at.isoformat() if ws.created_at else datetime.now(timezone.utc).isoformat(),
                            started_at=ws.updated_at.isoformat() if ws.updated_at else None,
                            metadata={"app_id": ws.app_id, "folder_path": ws.folder_path},
                        )
        except Exception as dev_err:
            logger.debug("Dev workspace discovery error: %s", dev_err)

        results = list(combined.values())

        # Filtering
        if workspace_id:
            results = [r for r in results if not r.workspace_id or r.workspace_id == workspace_id]
        if consumer_module:
            results = [r for r in results if r.consumer_module.lower() == consumer_module.lower()]
        if status:
            results = [r for r in results if r.status.value.lower() == status.lower()]

        # Sort newest first
        results.sort(key=lambda x: x.created_at or "", reverse=True)
        return results

    def terminate_sandbox(self, sandbox_id: str) -> bool:
        """Terminate and clean up sandbox compute."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            instance = self.find_active_sandbox(sandbox_id=sandbox_id, consumer_key=sandbox_id)
        if not instance:
            self._instances.pop(sandbox_id, None)
            return True
        driver = self._get_driver_for_mode(instance.runtime_mode)
        ok = driver.terminate(instance)
        instance.status = SandboxStatus.TERMINATED
        self._instances.pop(sandbox_id, None)
        self._instances.pop(instance.id, None)
        return ok

    def suspend_sandbox(self, sandbox_id: str) -> bool:
        """Suspend sandbox compute."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            return False
        driver = self._get_driver_for_mode(instance.runtime_mode)
        ok = driver.suspend(instance)
        if ok:
            instance.status = SandboxStatus.SUSPENDED
        return ok

    def resume_sandbox(self, sandbox_id: str) -> bool:
        """Resume suspended sandbox compute."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            return False
        driver = self._get_driver_for_mode(instance.runtime_mode)
        ok = driver.resume(instance)
        if ok:
            instance.status = SandboxStatus.RUNNING
        return ok

    def exec_in_sandbox(
        self,
        sandbox_id: str,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute a command in an active sandbox."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            return ExecResult(
                exit_code=1,
                stderr=f"Sandbox '{sandbox_id}' not found",
                success=False,
            )
        driver = self._get_driver_for_mode(instance.runtime_mode)
        return driver.exec_command(
            instance,
            command=command,
            working_dir=working_dir or instance.working_dir,
            env=env,
            timeout=timeout,
        )

    def get_sandbox_logs(self, sandbox_id: str, max_lines: int = 200) -> str:
        """Fetch logs from sandbox."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            return f"[Sandbox '{sandbox_id}' not found]"
        driver = self._get_driver_for_mode(instance.runtime_mode)
        return driver.get_logs(instance, max_lines=max_lines)

    async def stream_sandbox_logs(self, sandbox_id: str, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        """Stream logs from sandbox."""
        instance = self.get_sandbox(sandbox_id)
        if not instance:
            yield f"[Sandbox '{sandbox_id}' not found]\n"
            return
        driver = self._get_driver_for_mode(instance.runtime_mode)
        async for line in driver.stream_logs(instance, tail_lines=tail_lines):
            yield line

    async def handle_terminal_websocket(
        self,
        websocket: Any,
        sandbox_id: str,
        cols: int = 100,
        rows: int = 30,
        working_dir: Optional[str] = None,
        command: Optional[str] = None,
    ) -> None:
        """Bridge browser WebSocket with the live interactive PTY terminal of any sandbox."""
        import json
        from starlette.websockets import WebSocketState, WebSocketDisconnect

        await websocket.accept()

        instance = self.get_sandbox(sandbox_id)
        if not instance:
            instance = self.find_active_sandbox(sandbox_id=sandbox_id, consumer_key=sandbox_id)

        if not instance:
            err_msg = f"\r\n\x1b[1;31m[ERROR] Sandbox '{sandbox_id}' not found.\x1b[0m\r\n"
            try:
                await websocket.send_text(err_msg)
                await websocket.close(code=4404, reason=f"Sandbox '{sandbox_id}' not found")
            except Exception:
                pass
            return

        driver = self._get_driver_for_mode(instance.runtime_mode)

        welcome_banner = (
            f"\r\n\x1b[1;35m╭──────────────────────────────────────────────────────────╮\x1b[0m\r\n"
            f"\x1b[1;35m│\x1b[0m \x1b[1;32m● Connected to Sandbox Terminal\x1b[0m                          \x1b[1;35m│\x1b[0m\r\n"
            f"\x1b[1;35m│\x1b[0m Name: \x1b[1;36m{instance.name[:25]:<25}\x1b[0m Module: \x1b[1;33m{instance.consumer_module[:15]:<15}\x1b[0m \x1b[1;35m│\x1b[0m\r\n"
            f"\x1b[1;35m│\x1b[0m ID:   \x1b[90m{instance.id[:45]:<45}\x1b[0m \x1b[1;35m│\x1b[0m\r\n"
            f"\x1b[1;35m╰──────────────────────────────────────────────────────────╯\x1b[0m\r\n\r\n"
        )
        try:
            await websocket.send_text(welcome_banner)
        except Exception:
            return

        client_stream = driver.open_terminal_stream(
            instance,
            cols=cols,
            rows=rows,
            working_dir=working_dir,
            command=command,
        )

        if not client_stream:
            err_msg = "\r\n\x1b[1;31m[ERROR] Failed to attach interactive terminal. Is the sandbox container/pod running?\x1b[0m\r\n"
            try:
                await websocket.send_text(err_msg)
                await websocket.close(code=1011, reason="Sandbox container not reachable")
            except Exception:
                pass
            return

        is_k8s_ws = hasattr(client_stream, "write_stdin") and hasattr(client_stream, "read_stdout")
        if is_k8s_ws:
            from kubernetes.stream.ws_client import RESIZE_CHANNEL
            stop_event = asyncio.Event()

            async def pod_to_browser():
                loop = asyncio.get_running_loop()
                try:
                    while not stop_event.is_set():
                        if websocket.client_state != WebSocketState.CONNECTED or not client_stream.is_open():
                            break
                        chunk = await loop.run_in_executor(None, client_stream.read_stdout, 0.05)
                        if chunk:
                            await websocket.send_text(chunk)
                        else:
                            err_chunk = await loop.run_in_executor(None, client_stream.read_stderr, 0.02)
                            if err_chunk:
                                await websocket.send_text(err_chunk)
                            else:
                                await asyncio.sleep(0.02)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Sandbox pod to browser pipe ended: %s", e)
                finally:
                    stop_event.set()

            async def browser_to_pod():
                try:
                    while not stop_event.is_set() and client_stream.is_open():
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break

                        raw = message.get("text")
                        if raw is not None:
                            if not raw:
                                continue
                            if raw.startswith('{"type":') or raw.startswith('{"cols":'):
                                try:
                                    data = json.loads(raw)
                                    msg_type = data.get("type")
                                    if msg_type == "resize" or ("cols" in data and "rows" in data):
                                        c = int(data.get("cols", 80))
                                        r = int(data.get("rows", 24))
                                        client_stream.write_channel(RESIZE_CHANNEL, json.dumps({"Width": c, "Height": r}))
                                        continue
                                    elif msg_type == "ping":
                                        await websocket.send_text(json.dumps({"type": "pong"}))
                                        continue
                                except Exception:
                                    pass
                            client_stream.write_stdin(raw)
                        elif "bytes" in message:
                            raw_bytes = message["bytes"]
                            if raw_bytes:
                                client_stream.write_stdin(raw_bytes.decode("utf-8", errors="replace"))
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Browser to sandbox pod pipe ended: %s", e)
                finally:
                    stop_event.set()

            try:
                await asyncio.gather(pod_to_browser(), browser_to_pod(), return_exceptions=True)
            finally:
                try:
                    client_stream.close()
                except Exception:
                    pass
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
        else:
            # Subprocess (Docker / Local)
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()

            async def proc_to_browser():
                def _read_chunk():
                    try:
                        read_fn = getattr(client_stream.stdout, "read1", client_stream.stdout.read)
                        return read_fn(1024)
                    except Exception as ex:
                        logger.debug("Stdout read exception: %s", ex)
                        return b""

                try:
                    while not stop_event.is_set() and client_stream.poll() is None:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        data = await loop.run_in_executor(None, _read_chunk)
                        if data:
                            await websocket.send_bytes(data)
                        else:
                            if client_stream.poll() is not None:
                                break
                            await asyncio.sleep(0.02)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Sandbox subprocess stdout pipe ended: %s", e)
                finally:
                    stop_event.set()

            async def browser_to_proc():
                try:
                    while not stop_event.is_set() and client_stream.poll() is None:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break

                        raw = message.get("text")
                        if raw is not None:
                            if not raw:
                                continue
                            if raw.startswith('{"type":') or raw.startswith('{"cols":'):
                                try:
                                    data = json.loads(raw)
                                    if data.get("type") == "ping":
                                        await websocket.send_text(json.dumps({"type": "pong"}))
                                        continue
                                    if data.get("type") == "resize" or ("cols" in data and "rows" in data):
                                        c = int(data.get("cols", 100))
                                        r = int(data.get("rows", 30))
                                        driver.resize_terminal(instance, c, r)
                                        continue
                                except Exception:
                                    pass

                            if client_stream.stdin and not client_stream.stdin.closed:
                                client_stream.stdin.write(raw.encode("utf-8"))
                                client_stream.stdin.flush()
                        elif "bytes" in message:
                            raw_bytes = message["bytes"]
                            if raw_bytes and client_stream.stdin and not client_stream.stdin.closed:
                                client_stream.stdin.write(raw_bytes)
                                client_stream.stdin.flush()
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Browser to sandbox stdin pipe ended: %s", e)
                finally:
                    stop_event.set()

            try:
                await asyncio.gather(proc_to_browser(), browser_to_proc(), return_exceptions=True)
            finally:
                try:
                    if client_stream.poll() is None:
                        client_stream.terminate()
                except Exception:
                    pass
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.close()
                    except Exception:
                        pass


sandbox_service = SandboxService()
