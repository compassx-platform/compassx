"""Docker infrastructure driver for the Sandbox Module."""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid

from app.sandbox.interfaces import BaseSandboxDriver
from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec, SandboxStatus
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_IMAGE = "compassx-sandbox-host:latest"


class DockerSandboxDriver(BaseSandboxDriver):
    """Manages isolated compute sandboxes as Docker containers."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    def _resolve_image(self, client, requested_image: Optional[str]) -> str:
        """Resolve an existing local image or pull from registry with smart fallbacks."""
        candidates = []
        if requested_image:
            candidates.append(requested_image)
        candidates.extend([
            "compassx-sandbox-host:latest",
            "compassx-dev-host:latest",
            "compassx-host:latest",
            "python:3.11-slim",
            "node:20-slim",
            "alpine:latest",
        ])
        for img in candidates:
            try:
                client.images.get(img)
                return img
            except Exception:
                pass

        # Try pulling requested image or fallback
        target = requested_image or DEFAULT_SANDBOX_IMAGE
        try:
            logger.info("Pulling sandbox image %s...", target)
            client.images.pull(target)
            return target
        except Exception as pull_err:
            logger.warning("Could not pull image %s (will attempt run): %s", target, pull_err)
            return target

    def provision(self, spec: SandboxSpec) -> SandboxInstance:
        """Create and start a Docker container according to SandboxSpec."""
        import os
        client = self._get_client()
        sandbox_id = spec.sandbox_id or f"sb-{uuid.uuid4().hex[:10]}"
        container_name = f"compassx-sandbox-{sandbox_id}"
        image_name = self._resolve_image(client, spec.image)

        # 1. Prepare mounts and ensure source directories exist
        volumes = {}
        for mount in spec.storage_mounts:
            if mount.source_path and not os.path.exists(mount.source_path):
                try:
                    os.makedirs(mount.source_path, exist_ok=True)
                except Exception:
                    pass
            mode = "ro" if mount.read_only else "rw"
            volumes[mount.source_path] = {"bind": mount.mount_path, "mode": mode}

        # 3. Prepare port bindings
        ports_dict = {}
        for port in spec.ports:
            ports_dict[f"{port}/tcp"] = None  # Docker auto-assigns host port

        # 4. Prepare labels
        labels = {
            "compassx.sandbox": "true",
            "compassx.sandbox_id": sandbox_id,
            "compassx.sandbox_name": spec.name,
            "compassx.consumer_module": spec.consumer_module,
            "compassx.workspace_id": spec.workspace_id or "",
            "compassx.created_at": datetime.now(timezone.utc).isoformat(),
        }
        if spec.labels:
            labels.update(spec.labels)

        # 5. Resource limits
        kwargs = {
            "name": container_name,
            "detach": True,
            "environment": spec.env_vars,
            "volumes": volumes,
            "ports": ports_dict,
            "labels": labels,
            "working_dir": spec.working_dir or "/workspace",
            "command": ["tail", "-f", "/dev/null"],  # Keep alive for interactive exec
            "extra_hosts": {"host.docker.internal": "host-gateway"},
        }
        sandbox_network = os.environ.get("COMPASSX_SANDBOX_NETWORK", "").strip()
        if sandbox_network:
            kwargs["network"] = sandbox_network
        if spec.memory_limit:
            kwargs["mem_limit"] = spec.memory_limit
        if spec.cpu_limit:
            try:
                kwargs["nano_cpus"] = int(float(spec.cpu_limit) * 1e9)
            except (ValueError, TypeError):
                pass

        # Check for existing container with same name
        try:
            existing = client.containers.get(container_name)
            existing.remove(force=True)
        except Exception:
            pass

        # 6. Run container
        container = client.containers.run(image_name, **kwargs)

        # Seed Antigravity credentials and workspace trust from host storage if available
        try:
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            token_storage_dir = os.path.join(backend_dir, "storage", "credentials", "antigravity")
            host_token_file = os.path.join(token_storage_dir, "antigravity-oauth-token")
            user_token_file = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
            source_token = host_token_file if os.path.isfile(host_token_file) else (user_token_file if os.path.isfile(user_token_file) else None)
            from app.ai_gateway.mcp.omnigent_sync import get_mcp_sync_shell_script
            mcp_sync_cmd = get_mcp_sync_shell_script()
            init_script = (
                "mkdir -p /root/.gemini/antigravity-cli /root/.gemini/antigravity /root/.config/antigravity /root/.gemini/config 2>/dev/null; "
                "python3 -c \"import json, os; doc = {'trustedFolders': ['/', '/workspaces', '/workspaces/*', '/workspace', '/workspace/*', '/app', '/current'], 'trustedWorkspaces': ['/', '/workspaces', '/workspaces/*', '/workspace', '/workspace/*', '/app', '/current'], 'trustAllWorkspaces': True}; [os.makedirs(os.path.dirname(p), exist_ok=True) or open(p, 'w').write(json.dumps(doc, indent=2)) for p in ['/root/.gemini/antigravity/trusted_folders.json', '/root/.gemini/antigravity-cli/trusted_workspaces.json', '/root/.gemini/trusted_folders.json', '/root/.config/antigravity/trusted_workspaces.json']]\" 2>/dev/null || true; "
                "if [ -f /usr/local/bin/agy ] && [ ! -f /usr/local/bin/agy-bin ]; then "
                "  mv /usr/local/bin/agy /usr/local/bin/agy-bin 2>/dev/null && "
                "  printf '#!/bin/sh\\nexport AGY_TRUST_ALL=true ANTIGRAVITY_TRUST_ALL_WORKSPACES=true\\ncase \"$*\" in\\n  *--dangerously-skip-permissions*) exec /usr/local/bin/agy-bin \"$@\" ;;\\n  *) exec /usr/local/bin/agy-bin --dangerously-skip-permissions \"$@\" ;;\\nesac\\n' > /usr/local/bin/agy && chmod +x /usr/local/bin/agy 2>/dev/null || true; "
                "  ln -sf /usr/local/bin/agy /usr/local/bin/antigravity 2>/dev/null || true; "
                "fi; "
                f"{mcp_sync_cmd}; "
            )
            if source_token:
                import base64
                with open(source_token, "rb") as tf:
                    token_bytes = tf.read()
                b64 = base64.b64encode(token_bytes).decode("ascii")
                init_script += (
                    f"echo '{b64}' | base64 -d > /root/.gemini/antigravity-cli/antigravity-oauth-token 2>/dev/null && "
                    "cp -f /root/.gemini/antigravity-cli/antigravity-oauth-token /root/.gemini/oauth_creds.json 2>/dev/null || true; "
                )
            container.exec_run(f"/bin/sh -c \"{init_script}\"")
        except Exception as seed_err:
            logger.debug("Sandbox token seed notice: %s", seed_err)

        # 7. Resolve endpoints
        container.reload()
        endpoints = self._resolve_container_endpoints(container, spec.ports)

        instance = SandboxInstance(
            id=sandbox_id,
            name=spec.name,
            consumer_module=spec.consumer_module,
            workspace_id=spec.workspace_id,
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
            image=image_name,
            container_id=container.id,
            endpoints=endpoints,
            ports=spec.ports,
            working_dir=spec.working_dir or "/workspace",
            created_at=datetime.now(timezone.utc).isoformat(),
            started_at=datetime.now(timezone.utc).isoformat(),
            labels=labels,
            metadata=spec.metadata,
        )
        return instance

    def _resolve_container_endpoints(self, container, ports: List[int]) -> Dict[str, str]:
        endpoints = {}
        network_settings = getattr(container, "attrs", {}).get("NetworkSettings", {})
        port_bindings = network_settings.get("Ports", {})
        for port in ports:
            port_key = f"{port}/tcp"
            bindings = port_bindings.get(port_key)
            if bindings and len(bindings) > 0:
                host_port = bindings[0].get("HostPort")
                if host_port:
                    endpoints[str(port)] = f"http://localhost:{host_port}"
        return endpoints

    def terminate(self, instance: SandboxInstance) -> bool:
        """Stop and remove Docker container."""
        try:
            client = self._get_client()
            container = self._find_container(instance)
            if container:
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass
                container.remove(force=True)
            instance.status = SandboxStatus.TERMINATED
            instance.stopped_at = datetime.now(timezone.utc).isoformat()
            return True
        except Exception as exc:
            logger.warning("Error terminating Docker sandbox %s: %s", instance.id, exc)
            return False

    def suspend(self, instance: SandboxInstance) -> bool:
        """Stop container to free compute resources without deleting."""
        try:
            container = self._find_container(instance)
            if container:
                container.stop(timeout=5)
                instance.status = SandboxStatus.SUSPENDED
                return True
        except Exception as exc:
            logger.warning("Error suspending Docker sandbox %s: %s", instance.id, exc)
        return False

    def resume(self, instance: SandboxInstance) -> bool:
        """Restart stopped container."""
        try:
            container = self._find_container(instance)
            if container:
                container.start()
                container.reload()
                instance.status = SandboxStatus.RUNNING
                instance.endpoints = self._resolve_container_endpoints(container, instance.ports)
                return True
        except Exception as exc:
            logger.warning("Error resuming Docker sandbox %s: %s", instance.id, exc)
        return False

    def get_status(self, instance: SandboxInstance) -> SandboxStatus:
        """Get live container status."""
        try:
            container = self._find_container(instance)
            if not container:
                return SandboxStatus.TERMINATED
            container.reload()
            state = container.attrs.get("State", {}).get("Status", "").lower()
            if state == "running":
                return SandboxStatus.RUNNING
            elif state in ("paused", "exited", "stopped"):
                return SandboxStatus.SUSPENDED
            elif state in ("dead", "removing"):
                return SandboxStatus.FAILED
            elif state == "created":
                return SandboxStatus.PROVISIONING
        except Exception:
            return SandboxStatus.FAILED
        return SandboxStatus.RUNNING

    def exec_command(
        self,
        instance: SandboxInstance,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute command inside Docker container."""
        start_time = time.time()
        container = self._find_container(instance)
        if not container:
            return ExecResult(
                exit_code=1,
                stderr=f"Sandbox container {instance.id} not found",
                duration_seconds=0.0,
                success=False,
            )

        if isinstance(command, list):
            cmd = command
        else:
            cmd = ["sh", "-c", command]

        exec_env = dict(env or {})
        exec_env.setdefault("AGY_TRUST_ALL", "true")
        exec_env.setdefault("ANTIGRAVITY_TRUST_ALL_WORKSPACES", "true")
        exec_env.setdefault("AGY_NON_INTERACTIVE", "true")

        try:
            exec_res = container.exec_run(
                cmd,
                workdir=working_dir or instance.working_dir,
                environment=exec_env,
                demux=True,
            )
            duration = round(time.time() - start_time, 3)
            stdout_bytes, stderr_bytes = exec_res.output if isinstance(exec_res.output, tuple) else (exec_res.output, b"")
            stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            return ExecResult(
                exit_code=exec_res.exit_code,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=(exec_res.exit_code == 0),
            )
        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            return ExecResult(
                exit_code=1,
                stderr=f"Exec failed: {exc}",
                duration_seconds=duration,
                success=False,
            )

    def get_logs(self, instance: SandboxInstance, max_lines: int = 200) -> str:
        """Fetch Docker logs."""
        container = self._find_container(instance)
        if not container:
            return f"[Sandbox {instance.id} not running or not found]"
        try:
            logs = container.logs(tail=max_lines, stdout=True, stderr=True)
            return logs.decode("utf-8", errors="replace")
        except Exception as exc:
            return f"[Error fetching logs: {exc}]"

    async def stream_logs(self, instance: SandboxInstance, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        """Stream Docker container logs."""
        container = self._find_container(instance)
        if not container:
            yield f"[Sandbox {instance.id} container not found]\n"
            return
        try:
            log_stream = container.logs(stream=True, follow=True, tail=tail_lines, stdout=True, stderr=True)
            for chunk in log_stream:
                line = chunk.decode("utf-8", errors="replace")
                yield line
                await asyncio.sleep(0.01)
        except Exception as exc:
            yield f"[Log stream error: {exc}]\n"

    def get_endpoints(self, instance: SandboxInstance) -> Dict[str, str]:
        container = self._find_container(instance)
        if container:
            try:
                container.reload()
                return self._resolve_container_endpoints(container, instance.ports)
            except Exception:
                pass
        return instance.endpoints

    def discover_active_instances(self) -> List[SandboxInstance]:
        """Scan Docker for running sandboxes labeled with compassx.sandbox=true."""
        instances = []
        try:
            client = self._get_client()
            containers = client.containers.list(all=True, filters={"label": "compassx.sandbox=true"})
            for c in containers:
                labels = c.labels or {}
                sb_id = labels.get("compassx.sandbox_id") or c.name.replace("compassx-sandbox-", "")
                sb_name = labels.get("compassx.name") or sb_id
                consumer = labels.get("compassx.consumer_module") or "app"
                ws_id = labels.get("compassx.workspace_id")
                state = c.attrs.get("State", {}).get("Status", "").lower()
                if state == "running":
                    status = SandboxStatus.RUNNING
                elif state == "paused":
                    status = SandboxStatus.SUSPENDED
                elif state in ("exited", "stopped"):
                    status = SandboxStatus.STOPPED
                elif state in ("dead", "removing"):
                    status = SandboxStatus.TERMINATED
                else:
                    status = SandboxStatus.PROVISIONING
                created_at = labels.get("compassx.created_at") or c.attrs.get("Created", "")

                ports = []
                for p_str in c.attrs.get("NetworkSettings", {}).get("Ports", {}).keys():
                    try:
                        ports.append(int(p_str.split("/")[0]))
                    except Exception:
                        pass

                endpoints = self._resolve_container_endpoints(c, ports)

                instances.append(
                    SandboxInstance(
                        id=sb_id,
                        name=sb_name,
                        consumer_module=consumer,
                        workspace_id=ws_id,
                        status=status,
                        runtime_mode="docker",
                        image=c.image.tags[0] if c.image.tags else str(c.image.id)[:12],
                        container_id=c.id,
                        endpoints=endpoints,
                        ports=ports,
                        created_at=created_at,
                        started_at=c.attrs.get("State", {}).get("StartedAt"),
                        labels=labels,
                    )
                )
        except Exception as exc:
            logger.debug("Docker sandbox discovery failed: %s", exc)
        return instances

    def _find_container(self, instance: SandboxInstance):
        client = self._get_client()
        if instance.container_id:
            try:
                return client.containers.get(instance.container_id)
            except Exception:
                pass
        container_name = f"compassx-sandbox-{instance.id}"
        try:
            return client.containers.get(container_name)
        except Exception:
            return None

    def open_terminal_stream(
        self,
        instance: SandboxInstance,
        cols: int = 100,
        rows: int = 30,
        working_dir: Optional[str] = None,
        command: Optional[str] = None,
        agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Any:
        """Start a subprocess for Docker interactive exec into the sandbox container."""
        import subprocess
        container = self._find_container(instance)
        if not container:
            return None

        target_container = container.id
        workdir = working_dir or instance.working_dir or "/workspace"

        resolved_agent = (agent or "").lower().strip()
        cli_cmd = command
        if not cli_cmd:
            if resolved_agent in ("antigravity", "agy"):
                sess_f = f"/root/.gemini/sessions/{session_id}.conv_id" if session_id else ""
                cli_cmd = (
                    "export AGY_TRUST_ALL=true ANTIGRAVITY_TRUST_ALL_WORKSPACES=true AGY_NON_INTERACTIVE=true; "
                    f"if [ -n \"{sess_f}\" ] && [ -f \"{sess_f}\" ] && [ -n \"$(cat '{sess_f}' 2>/dev/null)\" ]; then "
                    f"  exec agy --dangerously-skip-permissions --conversation \"$(cat '{sess_f}')\"; "
                    f"else "
                    f"  exec agy --dangerously-skip-permissions; "
                    f"fi"
                )
            elif resolved_agent == "pi":
                cli_cmd = "pi --approve"
            elif resolved_agent == "opencode":
                cli_cmd = "opencode"
            elif resolved_agent in ("bash", "shell", "sh"):
                cli_cmd = "if [ -x /bin/bash ]; then exec /bin/bash -l; else exec /bin/sh -l; fi"
            else:
                cli_cmd = "if [ -x /bin/bash ]; then exec /bin/bash -l; else exec /bin/sh -l; fi"

        if session_id and resolved_agent and resolved_agent not in ("bash", "shell", "sh"):
            tmux_target = f"cx_{session_id.replace('-', '_')}"
            clean_cmd = cli_cmd.replace("'", "'\\''")
            cli_cmd = (
                f"(which tmux >/dev/null 2>&1 && tmux new-session -A -D -s '{tmux_target}' -c '{workdir}' '{clean_cmd} || exec /bin/bash -l') "
                f"|| ( {cli_cmd} )"
            )

        prep_cmd = (
            "export AGY_TRUST_ALL=true ANTIGRAVITY_TRUST_ALL_WORKSPACES=true AGY_NON_INTERACTIVE=true; "
            "alias agy='agy --dangerously-skip-permissions' 2>/dev/null || true; "
            "alias antigravity='agy --dangerously-skip-permissions' 2>/dev/null || true; "
            "if [ ! -f /root/.tmux.conf ]; then printf 'set -g mouse on\\nset -s set-clipboard on\\nset -g allow-passthrough on\\nset -g status off\\n' > /root/.tmux.conf 2>/dev/null || true; fi; "
        )
        full_cli = f"{prep_cmd}{cli_cmd}"

        py_pty_script = (
            "import pty, os, sys, fcntl, termios, struct; "
            f"cols = int(os.environ.get('COLUMNS', {cols})); "
            f"rows = int(os.environ.get('LINES', {rows})); "
            "pid, m = pty.fork(); "
            "("
            f"    os.execlp('sh', 'sh', '-c', '{full_cli}') if pid == 0 else ("
            "        fcntl.ioctl(m, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0)), "
            "        pty._copy(m, pty._read, pty._read), "
            "        os.close(m), "
            "        os.waitpid(pid, 0)"
            "    )"
            ")"
        )
        cmd = [
            "docker", "exec", "-i", "-w", workdir,
            "-e", f"COLUMNS={cols}", "-e", f"LINES={rows}",
            "-e", "TERM=xterm-256color",
            target_container,
            "python3", "-c", py_pty_script,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            return proc
        except Exception as exc:
            logger.warning("Failed to start docker interactive terminal for sandbox %s: %s", instance.id, exc)
            # Fallback to direct shell without python3 pty wrapper
            try:
                cmd_fallback = [
                    "docker", "exec", "-i", "-w", workdir,
                    "-e", f"COLUMNS={cols}", "-e", f"LINES={rows}",
                    "-e", "TERM=xterm-256color",
                    target_container,
                    "sh", "-c", cli_cmd,
                ]
                return subprocess.Popen(
                    cmd_fallback,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                )
            except Exception as ex2:
                logger.error("Fallback docker exec failed for sandbox %s: %s", instance.id, ex2)
                return None

    def resize_terminal(
        self,
        instance: SandboxInstance,
        cols: int,
        rows: int,
    ) -> None:
        """Resize terminal dimensions."""
        pass
