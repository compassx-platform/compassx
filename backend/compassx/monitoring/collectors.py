from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import psutil

from compassx.models import ServiceMode
from compassx.monitoring.models import ObservedResource
from compassx.registry import DeploymentProfile


def _uptime(started: datetime | None) -> str:
    if started is None:
        return "-"
    seconds = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return f"{days}d {hours}h" if days else f"{hours}h {minutes}m"


class ResourceCollector(ABC):
    @abstractmethod
    def collect(self) -> list[ObservedResource]: ...


class HostCollector(ResourceCollector):
    """Actual host utilization for profiles whose backend runs locally."""

    def __init__(self) -> None:
        self._previous: tuple[float, object, object] | None = None

    def collect(self) -> list[ObservedResource]:
        now = time.monotonic()
        network = psutil.net_io_counters()
        disk_io = psutil.disk_io_counters()
        elapsed = now - self._previous[0] if self._previous else 0

        def rate(current: int, previous: int) -> float:
            return max(0, current - previous) / elapsed / 1024 if elapsed > 0 else 0

        net_in = net_out = disk_read = disk_write = 0.0
        if self._previous:
            old_network, old_disk = self._previous[1], self._previous[2]
            net_in = rate(network.bytes_recv, old_network.bytes_recv)
            net_out = rate(network.bytes_sent, old_network.bytes_sent)
            if disk_io and old_disk:
                disk_read = rate(disk_io.read_bytes, old_disk.read_bytes)
                disk_write = rate(disk_io.write_bytes, old_disk.write_bytes)
        self._previous = (now, network, disk_io)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(Path.cwd().anchor or os.sep)
        boot = datetime.fromtimestamp(psutil.boot_time(), timezone.utc)
        return [ObservedResource(
            id="local-host", name="Local host", kind="node", status="Healthy",
            runtime="Local", uptime=_uptime(boot), cpu_percent=round(psutil.cpu_percent(), 2),
            memory_percent=round(memory.percent, 2), memory_mb=round(memory.used / 1024**2, 2),
            disk_percent=round(disk.percent, 2), network_in_kbps=round(net_in, 2),
            network_out_kbps=round(net_out, 2), disk_read_kbps=round(disk_read, 2),
            disk_write_kbps=round(disk_write, 2), health="Healthy", start_time=boot,
        )]


class LocalProcessCollector(ResourceCollector):
    """Samples native services recorded by LocalProcessLauncher."""

    def __init__(self, profile: DeploymentProfile, repo_root: Path) -> None:
        self._profile = profile
        self._state_dir = repo_root / ".compassx" / "services"
        self._processes: dict[int, psutil.Process] = {}

    def collect(self) -> list[ObservedResource]:
        resources = []
        for name, entry in self._profile.services.items():
            if entry.mode != ServiceMode.LOCAL:
                continue
            path = self._state_dir / f"{name}.json"
            try:
                pid = int(json.loads(path.read_text(encoding="utf-8"))["pid"])
                process = self._processes.setdefault(pid, psutil.Process(pid))
                processes = [process, *process.children(recursive=True)]
                memory_bytes = sum(item.memory_info().rss for item in processes)
                cpu = sum(item.cpu_percent() for item in processes) / max(psutil.cpu_count(), 1)
                created = datetime.fromtimestamp(process.create_time(), timezone.utc)
                resources.append(ObservedResource(
                    id=f"process:{name}", name=name.replace("-", " ").title(), kind="service",
                    status="Running", runtime="Local process", uptime=_uptime(created),
                    cpu_percent=round(cpu, 2),
                    memory_percent=round(memory_bytes / psutil.virtual_memory().total * 100, 2),
                    memory_mb=round(memory_bytes / 1024**2, 2), health="Healthy", start_time=created,
                ))
            except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError, psutil.Error):
                resources.append(ObservedResource(
                    id=f"process:{name}",
                    name=name.replace("-", " ").title(),
                    kind="service",
                    status="Stopped",
                    runtime="Local process",
                    uptime="-",
                    health="Stopped",
                ))
        return resources


class DockerComposeCollector(ResourceCollector):
    """Samples containers belonging to the active profile's Compose project."""

    def __init__(self, project: str, client=None) -> None:
        if client is None:
            import docker
            # Monitoring must never hold an API request open for Docker's
            # long default timeout. A missed sample is safer than blocking
            # health checks and subsequent Prometheus scrapes.
            client = docker.from_env(timeout=2.5)
        self._client = client
        self._project = project
        self._previous: dict[str, tuple[float, dict]] = {}

    @staticmethod
    def _cpu_percent(stats: dict) -> float:
        cpu = stats.get("cpu_stats", {})
        previous = stats.get("precpu_stats", {})
        cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - previous.get("cpu_usage", {}).get("total_usage", 0)
        system_delta = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
        count = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
        return cpu_delta / system_delta * count * 100 if system_delta > 0 and cpu_delta >= 0 else 0

    def collect(self) -> list[ObservedResource]:
        containers = self._client.containers.list(
            all=True, filters={"label": f"com.docker.compose.project={self._project}"}
        )
        resources = []
        for container in containers:
            labels = container.labels or {}
            service = labels.get("com.docker.compose.service") or container.name
            if labels.get("com.docker.compose.oneoff") == "True" or service.endswith("-init"):
                continue
            running = container.status == "running"
            # Container status discovery is safe in the scrape path, but Docker
            # Desktop's stats endpoint leaves orphaned CLI clients when a scrape
            # is cancelled. Container utilization must come from a dedicated
            # Prometheus exporter rather than recursively sampling Docker here.
            stats = {}
            now = time.monotonic()
            previous = self._previous.get(container.id)
            elapsed = now - previous[0] if previous else 0
            networks = stats.get("networks") or {}
            net_in_total = sum(item.get("rx_bytes", 0) for item in networks.values())
            net_out_total = sum(item.get("tx_bytes", 0) for item in networks.values())
            blk = stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
            read_total = sum(item.get("value", 0) for item in blk if str(item.get("op", "")).lower() == "read")
            write_total = sum(item.get("value", 0) for item in blk if str(item.get("op", "")).lower() == "write")
            totals = {"in": net_in_total, "out": net_out_total, "read": read_total, "write": write_total}
            rates = {
                key: max(0, totals[key] - previous[1].get(key, 0)) / elapsed / 1024
                if previous and elapsed > 0 else 0 for key in totals
            }
            self._previous[container.id] = (now, totals)
            memory = stats.get("memory_stats") or {}
            usage = max(0, memory.get("usage", 0) - memory.get("stats", {}).get("inactive_file", 0))
            limit = memory.get("limit", 0)
            state = (container.attrs or {}).get("State", {})
            started = _parse_datetime(state.get("StartedAt")) if running else None
            health = (state.get("Health") or {}).get("Status", "healthy" if running else "stopped")
            image = ((container.attrs or {}).get("Config") or {}).get("Image")
            resources.append(ObservedResource(
                id=f"docker:{service}", name=service.replace("-", " ").title(), kind="service",
                status=container.status.title(), runtime="Docker", uptime=_uptime(started),
                cpu_percent=round(self._cpu_percent(stats), 2),
                memory_percent=round(usage / limit * 100, 2) if limit else 0,
                memory_mb=round(usage / 1024**2, 2), network_in_kbps=round(rates["in"], 2),
                network_out_kbps=round(rates["out"], 2), disk_read_kbps=round(rates["read"], 2),
                disk_write_kbps=round(rates["write"], 2),
                restart_count=int((container.attrs or {}).get("RestartCount", 0)), health=health.title(),
                start_time=started, container_name=container.name, image_version=image,
            ))
        return sorted(resources, key=lambda item: item.name)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
