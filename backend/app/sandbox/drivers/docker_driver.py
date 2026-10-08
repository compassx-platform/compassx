"""Docker infrastructure driver for the Sandbox Module."""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional
import uuid

from app.sandbox.interfaces import BaseSandboxDriver
from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec, SandboxStatus
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_IMAGE = "compassx-dev-host:latest"


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
            "compassx-dev-host:latest",
            "compassx-host:latest",
            "ghcr.io/omnigent-ai/omnigent-host:latest",
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
        }
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

        try:
            exec_res = container.exec_run(
                cmd,
                workdir=working_dir or instance.working_dir,
                environment=env,
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
