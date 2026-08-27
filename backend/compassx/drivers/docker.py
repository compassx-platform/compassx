"""Docker Driver — runs runtimes as Docker containers via the Docker SDK.

infra_id == container ID. Containers are labelled with the runtime ID so
they can be rediscovered after restarts.
"""

from __future__ import annotations

import asyncio
import io
import logging
import tarfile
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from compassx.interfaces.driver import ResourceDriver
from compassx.models import (
    DriverUnavailableError,
    ExecResult,
    RuntimeAlreadyExistsError,
    RuntimeInfo,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeProvisionError,
    RuntimeSpec,
)
from compassx.models.runtime import (
    MANAGED_BY_LABEL,
    MANAGED_BY_VALUE,
    RUNTIME_ID_LABEL,
    RUNTIME_TYPE_LABEL,
)

logger = logging.getLogger(__name__)

_STATUS_TO_PHASE = {
    "created": RuntimePhase.PENDING,
    "restarting": RuntimePhase.PENDING,
    "running": RuntimePhase.RUNNING,
    "paused": RuntimePhase.SUSPENDED,
    "exited": RuntimePhase.STOPPED,
    "dead": RuntimePhase.FAILED,
    "removing": RuntimePhase.STOPPING,
}


class DockerDriver(ResourceDriver):
    name = "docker"

    def __init__(
        self,
        network: str | None = None,
        project_name: str | None = None,
        client=None,
    ) -> None:
        """network: docker network to attach runtimes to (e.g. compassx_default).
        project_name: docker compose project name for grouping in Docker Desktop."""
        try:
            import docker  # noqa: PLC0415 - optional dependency
            from docker.errors import DockerException
        except ImportError as exc:  # pragma: no cover
            raise DriverUnavailableError(
                "docker SDK not installed. `pip install docker`."
            ) from exc
        self._errors = __import__("docker.errors", fromlist=["errors"])
        if client is not None:
            self._client = client
        else:
            try:
                self._client = docker.from_env()
            except DockerException as exc:
                raise DriverUnavailableError(
                    f"Docker daemon not reachable: {exc}"
                ) from exc
        self._network = network
        self._project_name = project_name

    # ── helpers ──────────────────────────────────────────────────────────

    def _find_container(self, runtime_id: str):
        containers = self._client.containers.list(
            all=True, filters={"label": f"{RUNTIME_ID_LABEL}={runtime_id}"}
        )
        if not containers:
            raise RuntimeNotFoundError(f"Docker runtime not found: {runtime_id}")
        return containers[0]

    @staticmethod
    def _to_nano_cpus(cpu: str | None) -> int | None:
        if not cpu:
            return None
        cpu = cpu.strip()
        if cpu.endswith("m"):
            return int(float(cpu[:-1]) * 1_000_000)
        return int(float(cpu) * 1_000_000_000)

    @staticmethod
    def _to_bytes(mem: str | None) -> str | None:
        if not mem:
            return None
        mem = mem.strip()
        # docker SDK accepts strings like "512m"/"2g"
        if mem.endswith("Gi"):
            return f"{mem[:-2]}g"
        if mem.endswith("Mi"):
            return f"{mem[:-2]}m"
        return mem

    def _info_from_container(self, container) -> RuntimeInfo:
        labels = container.labels or {}
        state = (container.attrs.get("State") or {}) if container.attrs else {}
        phase = _STATUS_TO_PHASE.get(container.status, RuntimePhase.UNKNOWN)
        message = ""
        if container.status == "exited":
            exit_code = state.get("ExitCode", 0)
            if exit_code:
                phase = RuntimePhase.FAILED
                message = state.get("Error") or f"Container exited with code {exit_code}"
        if state.get("OOMKilled"):
            phase = RuntimePhase.FAILED
            message = "Out of memory. Try a larger compute profile."
        return RuntimeInfo(
            runtime_id=labels.get(RUNTIME_ID_LABEL, ""),
            runtime_type=labels.get(RUNTIME_TYPE_LABEL, ""),
            phase=phase,
            infra_id=container.id,
            message=message,
            created_at=_parse_docker_time(container.attrs.get("Created")),
            started_at=_parse_docker_time(state.get("StartedAt")),
            finished_at=_parse_docker_time(state.get("FinishedAt")),
            labels=labels,
        )

    # ── lifecycle ────────────────────────────────────────────────────────

    async def create_runtime(self, spec: RuntimeSpec) -> str:
        try:
            self._find_container(spec.runtime_id)
        except RuntimeNotFoundError:
            pass
        else:
            raise RuntimeAlreadyExistsError(
                f"Docker runtime already exists: {spec.runtime_id}"
            )

        labels = {
            **spec.labels,
            RUNTIME_ID_LABEL: spec.runtime_id,
            RUNTIME_TYPE_LABEL: spec.runtime_type,
            MANAGED_BY_LABEL: MANAGED_BY_VALUE,
        }
        if self._project_name:
            labels["com.docker.compose.project"] = self._project_name
        environment = dict(spec.env)
        ports = {
            f"{p.container_port}/{p.protocol.lower()}": p.host_port
            for p in spec.ports
        }
        volumes = {}
        for v in spec.volumes:
            if v.host_path:
                volumes[v.host_path] = {
                    "bind": v.mount_path,
                    "mode": "ro" if v.read_only else "rw",
                }

        run_kwargs: dict = {
            "image": spec.container_image,
            "name": f"compassx-runtime-{spec.runtime_id}",
            "detach": True,
            "labels": labels,
            "environment": environment,
        }
        command = list(spec.command) + list(spec.args)
        if command:
            run_kwargs["command"] = command
        if ports:
            run_kwargs["ports"] = ports
        if volumes:
            run_kwargs["volumes"] = volumes
        if spec.working_dir:
            run_kwargs["working_dir"] = spec.working_dir
        if self._network:
            run_kwargs["network"] = self._network
        nano_cpus = self._to_nano_cpus(spec.resources.cpu_limit)
        if nano_cpus:
            run_kwargs["nano_cpus"] = nano_cpus
        mem = self._to_bytes(spec.resources.memory_limit)
        if mem:
            run_kwargs["mem_limit"] = mem

        def _run():
            return self._client.containers.run(**run_kwargs)

        try:
            container = await asyncio.to_thread(_run)
        except self._errors.ImageNotFound as exc:
            raise RuntimeProvisionError(
                f"Image not found: {spec.container_image}"
            ) from exc
        except self._errors.APIError as exc:
            raise RuntimeProvisionError(
                f"Docker failed to create runtime {spec.runtime_id}: {exc}"
            ) from exc
        logger.info(
            "Docker runtime created: runtime_id=%s container=%s image=%s",
            spec.runtime_id,
            container.short_id,
            spec.container_image,
        )
        return container.id

    async def start_runtime(self, runtime_id: str) -> None:
        container = self._find_container(runtime_id)
        try:
            await asyncio.to_thread(container.start)
        except self._errors.APIError as exc:
            raise RuntimeProvisionError(
                f"Failed to start runtime {runtime_id}: {exc}"
            ) from exc

    async def stop_runtime(self, runtime_id: str) -> None:
        container = self._find_container(runtime_id)
        try:
            await asyncio.to_thread(container.stop)
        except self._errors.APIError as exc:
            raise RuntimeProvisionError(
                f"Failed to stop runtime {runtime_id}: {exc}"
            ) from exc
        logger.info("Docker runtime stopped: runtime_id=%s", runtime_id)

    async def delete_runtime(self, runtime_id: str) -> None:
        container = self._find_container(runtime_id)
        try:
            await asyncio.to_thread(container.remove, force=True)
        except self._errors.APIError as exc:
            raise RuntimeProvisionError(
                f"Failed to delete runtime {runtime_id}: {exc}"
            ) from exc
        logger.info("Docker runtime deleted: runtime_id=%s", runtime_id)

    # ── inspection ───────────────────────────────────────────────────────

    async def get_status(self, runtime_id: str) -> RuntimeInfo:
        container = self._find_container(runtime_id)
        container.reload()
        return self._info_from_container(container)

    async def list_runtimes(self) -> list[RuntimeInfo]:
        containers = self._client.containers.list(
            all=True, filters={"label": f"{MANAGED_BY_LABEL}={MANAGED_BY_VALUE}"}
        )
        return [self._info_from_container(c) for c in containers]

    # ── interaction ──────────────────────────────────────────────────────

    async def exec(self, runtime_id: str, command: list[str]) -> ExecResult:
        container = self._find_container(runtime_id)

        def _exec():
            return container.exec_run(command, demux=True)

        result = await asyncio.to_thread(_exec)
        stdout, stderr = result.output if result.output else (b"", b"")
        return ExecResult(
            exit_code=result.exit_code or 0,
            stdout=(stdout or b"").decode("utf-8", errors="replace"),
            stderr=(stderr or b"").decode("utf-8", errors="replace"),
        )

    async def logs(self, runtime_id: str, tail: int | None = None) -> str:
        container = self._find_container(runtime_id)
        raw = await asyncio.to_thread(
            container.logs, tail=tail if tail is not None else "all"
        )
        return raw.decode("utf-8", errors="replace")

    async def stream_logs(self, runtime_id: str) -> AsyncIterator[str]:
        container = self._find_container(runtime_id)
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        sentinel = object()

        def _read():
            try:
                for raw_line in container.logs(stream=True, follow=True, tail=100):
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    if line:
                        asyncio.run_coroutine_threadsafe(queue.put(line), loop)
            except Exception as exc:  # noqa: BLE001 - relay stream errors
                asyncio.run_coroutine_threadsafe(
                    queue.put(f"[error] Log stream error: {exc}"), loop
                )
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop)

        import threading

        threading.Thread(target=_read, daemon=True).start()
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            yield item

    async def copy_file(
        self, runtime_id: str, src_path: str, dest_path: str, to_runtime: bool = True
    ) -> None:
        container = self._find_container(runtime_id)
        if to_runtime:
            src = Path(src_path)
            data = src.read_bytes()
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                info = tarfile.TarInfo(name=Path(dest_path).name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            buf.seek(0)
            await asyncio.to_thread(
                container.put_archive, str(Path(dest_path).parent.as_posix()), buf
            )
        else:
            stream, _stat = await asyncio.to_thread(container.get_archive, src_path)
            buf = io.BytesIO(b"".join(stream))
            with tarfile.open(fileobj=buf) as tar:
                member = tar.getmembers()[0]
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise RuntimeProvisionError(f"Cannot extract {src_path}")
                Path(dest_path).write_bytes(extracted.read())


def _parse_docker_time(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-01-01"):
        return None
    try:
        # Docker returns RFC3339 with nanoseconds; trim to microseconds.
        if "." in value:
            head, tail = value.split(".", 1)
            frac = "".join(ch for ch in tail if ch.isdigit())[:6]
            tz = tail[len(frac):] if len(tail) > len(frac) else ""
            tz = "".join(ch for ch in tail if not ch.isdigit() and ch != ".")
            value = f"{head}.{frac}{tz.replace('Z', '+00:00')}"
        else:
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        return None
