from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from threading import Event, Lock, Thread
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
            memory_limit_mb=round(memory.total / 1024**2, 2),
            disk_percent=round(disk.percent, 2), network_in_kbps=round(net_in, 2),
            network_out_kbps=round(net_out, 2), disk_read_kbps=round(disk_read, 2),
            disk_write_kbps=round(disk_write, 2), health="Healthy", start_time=boot,
            cpu_cores=float(psutil.cpu_count(logical=True) or 1.0),
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
                    memory_mb=round(memory_bytes / 1024**2, 2),
                    memory_limit_mb=round(psutil.virtual_memory().total / 1024**2, 2),
                    health="Healthy", start_time=created,
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
            client = docker.from_env(timeout=3.0)
        self._client = client
        self._project = project
        self._cached_stats: dict[str, tuple[float, dict, float, dict]] = {}
        self._stats_lock = Lock()
        self._stop_event = Event()
        self._sampler_thread = Thread(
            target=self._background_stats_loop,
            name=f"compassx-docker-sampler-{project}",
            daemon=True,
        )
        self._sampler_thread.start()

    def _sample_single_container_stats(self, container) -> None:
        try:
            stats = container.stats(stream=False)
            now = time.monotonic()
            with self._stats_lock:
                prev = self._cached_stats.get(container.id)
                prev_time = prev[0] if prev else now - 1.0
                prev_stats = prev[1] if prev else stats
                self._cached_stats[container.id] = (now, stats, prev_time, prev_stats)
        except Exception:
            pass

    def _background_stats_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                containers = self._client.containers.list(
                    all=False, filters={"label": f"com.docker.compose.project={self._project}"}
                )
                if containers:
                    with ThreadPoolExecutor(max_workers=min(10, len(containers))) as pool:
                        list(pool.map(self._sample_single_container_stats, containers))
            except Exception:
                pass
            self._stop_event.wait(4.0)

    @staticmethod
    def _cpu_percent(stats: dict) -> float:
        cpu = stats.get("cpu_stats", {})
        previous = stats.get("precpu_stats", {})
        cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - previous.get("cpu_usage", {}).get("total_usage", 0)
        system_delta = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
        count = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
        return round(cpu_delta / system_delta * count * 100, 2) if system_delta > 0 and cpu_delta >= 0 else 0.0

    def _sample_container(self, container) -> ObservedResource | None:
        labels = container.labels or {}
        service = labels.get("com.docker.compose.service") or container.name
        if (
            labels.get("com.docker.compose.oneoff") == "True"
            or service.endswith("-init")
            or service == "jobs-runner-image"
        ):
            return None
        running = container.status == "running"
        if not running and service in {"backend", "frontend"}:
            return None
        state = (container.attrs or {}).get("State", {})
        started = _parse_datetime(state.get("StartedAt")) if running else None
        health = (state.get("Health") or {}).get("Status", "healthy" if running else "stopped")
        image = ((container.attrs or {}).get("Config") or {}).get("Image")
        restart_count = int((container.attrs or {}).get("RestartCount", 0))

        cpu_percent = 0.0
        memory_percent = 0.0
        memory_mb = 0.0
        memory_limit_mb = 0.0
        network_in_kbps = 0.0
        network_out_kbps = 0.0
        disk_read_kbps = 0.0
        disk_write_kbps = 0.0

        if running:
            with self._stats_lock:
                cached = self._cached_stats.get(container.id)
            if cached:
                now_t, stats, prev_t, prev_stats = cached
                cpu_percent = self._cpu_percent(stats)

                memory = stats.get("memory_stats") or {}
                usage = max(0, memory.get("usage", 0) - memory.get("stats", {}).get("inactive_file", 0))
                limit = memory.get("limit", 0)
                memory_mb = round(usage / 1024**2, 2)
                host_mem_limit = (container.attrs or {}).get("HostConfig", {}).get("Memory", 0)
                if host_mem_limit and host_mem_limit > 0:
                    memory_limit_mb = round(host_mem_limit / 1024**2, 2)
                    memory_percent = round(usage / host_mem_limit * 100, 2)
                else:
                    memory_limit_mb = 0.0
                    memory_percent = round(usage / limit * 100, 2) if limit else 0.0

                elapsed = max(0.1, now_t - prev_t)
                nets = stats.get("networks") or {}
                prev_nets = prev_stats.get("networks") or {}
                rx = sum(n.get("rx_bytes", 0) for n in nets.values())
                prev_rx = sum(n.get("rx_bytes", 0) for n in prev_nets.values())
                tx = sum(n.get("tx_bytes", 0) for n in nets.values())
                prev_tx = sum(n.get("tx_bytes", 0) for n in prev_nets.values())
                network_in_kbps = round(max(0, rx - prev_rx) / elapsed / 1024, 2)
                network_out_kbps = round(max(0, tx - prev_tx) / elapsed / 1024, 2)

                blk = stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
                prev_blk = prev_stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
                read_bytes = sum(i.get("value", 0) for i in blk if str(i.get("op", "")).lower() == "read")
                prev_read_bytes = sum(i.get("value", 0) for i in prev_blk if str(i.get("op", "")).lower() == "read")
                write_bytes = sum(i.get("value", 0) for i in blk if str(i.get("op", "")).lower() == "write")
                prev_write_bytes = sum(i.get("value", 0) for i in prev_blk if str(i.get("op", "")).lower() == "write")
                disk_read_kbps = round(max(0, read_bytes - prev_read_bytes) / elapsed / 1024, 2)
                disk_write_kbps = round(max(0, write_bytes - prev_write_bytes) / elapsed / 1024, 2)

        return ObservedResource(
            id=f"docker:{service}",
            name=service.replace("-", " ").title(),
            kind="service",
            status=container.status.title(),
            runtime="Docker",
            uptime=_uptime(started),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            memory_limit_mb=memory_limit_mb if running else 0.0,
            network_in_kbps=network_in_kbps,
            network_out_kbps=network_out_kbps,
            disk_read_kbps=disk_read_kbps,
            disk_write_kbps=disk_write_kbps,
            restart_count=restart_count,
            health=health.title(),
            start_time=started,
            container_name=container.name,
            image_version=image,
        )

    def collect(self) -> list[ObservedResource]:
        containers = self._client.containers.list(
            all=True, filters={"label": f"com.docker.compose.project={self._project}"}
        )
        if not containers:
            return []
        with ThreadPoolExecutor(max_workers=min(12, len(containers))) as pool:
            results = pool.map(self._sample_container, containers)
        return sorted([r for r in results if r is not None], key=lambda item: item.name)


def _parse_k8s_cpu_cores(cpu_str: str | None) -> float:
    """Parse Kubernetes CPU usage string to cores as float."""
    if not cpu_str:
        return 0.0
    cpu_str = str(cpu_str).strip()
    try:
        if cpu_str.endswith("n"):
            return float(cpu_str[:-1]) / 1_000_000_000.0
        if cpu_str.endswith("u"):
            return float(cpu_str[:-1]) / 1_000_000.0
        if cpu_str.endswith("m"):
            return float(cpu_str[:-1]) / 1_000.0
        return float(cpu_str)
    except Exception:
        return 0.0


def _parse_k8s_memory_bytes(mem_str: str | None) -> float:
    """Parse Kubernetes memory usage/limit string to bytes as float."""
    if not mem_str:
        return 0.0
    mem_str = str(mem_str).strip()
    try:
        if mem_str.endswith("Ki"):
            return float(mem_str[:-2]) * 1024.0
        if mem_str.endswith("Mi"):
            return float(mem_str[:-2]) * 1024.0 * 1024.0
        if mem_str.endswith("Gi"):
            return float(mem_str[:-2]) * 1024.0 * 1024.0 * 1024.0
        if mem_str.endswith("Ti"):
            return float(mem_str[:-2]) * 1024.0 * 1024.0 * 1024.0 * 1024.0
        if mem_str.endswith("k"):
            return float(mem_str[:-1]) * 1000.0
        if mem_str.endswith("M"):
            return float(mem_str[:-1]) * 1000.0 * 1000.0
        if mem_str.endswith("G"):
            return float(mem_str[:-1]) * 1000.0 * 1000.0 * 1000.0
        return float(mem_str)
    except Exception:
        return 0.0


class KubernetesCollector(ResourceCollector):
    """Samples pods in the Kubernetes namespace for kubernetes profiles."""

    def __init__(self, namespace: str = "compassx", client=None) -> None:
        if client is None:
            from compassx.drivers.k8s_client import K8sApiClient
            client = K8sApiClient()
        self._client = client
        self._namespace = namespace

    def _fetch_pod_metrics(self) -> dict[str, dict[str, float]]:
        """Fetch live container CPU and Memory usage from metrics.k8s.io."""
        metrics_by_pod: dict[str, dict[str, float]] = {}
        try:
            from kubernetes import client as k8s_client
            cust = k8s_client.CustomObjectsApi()
            metrics_list = cust.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=self._namespace,
                plural="pods",
            )
            for item in metrics_list.get("items", []):
                pod_name = item.get("metadata", {}).get("name")
                total_cores = 0.0
                total_mem_bytes = 0.0
                for c in item.get("containers", []):
                    usage = c.get("usage", {})
                    total_cores += _parse_k8s_cpu_cores(usage.get("cpu"))
                    total_mem_bytes += _parse_k8s_memory_bytes(usage.get("memory"))
                metrics_by_pod[pod_name] = {
                    "cpu_percent": round(total_cores * 100.0, 2),  # 1 core = 100%
                    "memory_mb": round(total_mem_bytes / (1024.0 * 1024.0), 2),
                    "memory_bytes": total_mem_bytes,
                }
        except Exception as exc:
            logger.debug("metrics.k8s.io query notice for %s: %s", self._namespace, exc)
        return metrics_by_pod

    def _fetch_node_metrics(self) -> dict[str, dict[str, float]]:
        """Fetch live node CPU and Memory usage from metrics.k8s.io."""
        metrics_by_node: dict[str, dict[str, float]] = {}
        try:
            from kubernetes import client as k8s_client
            cust = k8s_client.CustomObjectsApi()
            metrics_list = cust.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
            )
            for item in metrics_list.get("items", []):
                node_name = item.get("metadata", {}).get("name")
                usage = item.get("usage", {})
                cores = _parse_k8s_cpu_cores(usage.get("cpu"))
                mem_bytes = _parse_k8s_memory_bytes(usage.get("memory"))
                metrics_by_node[node_name] = {
                    "cpu_percent": round(cores * 100.0, 2),
                    "memory_mb": round(mem_bytes / (1024.0 * 1024.0), 2),
                    "memory_bytes": mem_bytes,
                }
        except Exception as exc:
            logger.debug("metrics.k8s.io node query notice: %s", exc)
        return metrics_by_node

    def _collect_nodes(self) -> list[ObservedResource]:
        """Collect cluster nodes as kind='node' resources with allocatable memory limits."""
        nodes_res: list[ObservedResource] = []
        try:
            core_v1 = self._client.core()
            k8s_nodes = core_v1.list_node().items
        except Exception:
            return nodes_res

        node_metrics = self._fetch_node_metrics()

        for node in k8s_nodes:
            node_name = node.metadata.name or ""
            allocatable = node.status.allocatable or {}
            alloc_cores = _parse_k8s_cpu_cores(allocatable.get("cpu"))
            alloc_mem_bytes = _parse_k8s_memory_bytes(allocatable.get("memory"))
            alloc_mem_mb = round(alloc_mem_bytes / (1024.0 * 1024.0), 2)

            created = node.metadata.creation_timestamp
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            ready_cond = next((c for c in (node.status.conditions or []) if c.type == "Ready"), None)
            is_ready = bool(ready_cond and ready_cond.status == "True")
            status = "Ready" if is_ready else "NotReady"

            m = node_metrics.get(node_name, {})
            cpu_percent = m.get("cpu_percent", 0.0)
            mem_used_mb = m.get("memory_mb", 0.0)
            mem_used_bytes = m.get("memory_bytes", 0.0)
            mem_percent = (
                round(mem_used_bytes / alloc_mem_bytes * 100.0, 2)
                if alloc_mem_bytes > 0 and mem_used_bytes > 0
                else 0.0
            )

            labels = node.metadata.labels or {}
            mode = labels.get("kubernetes.azure.com/mode", "").lower()
            pool_label = labels.get("kubernetes.azure.com/agentpool")
            if not pool_label:
                parts = node_name.split("-")
                pool_label = parts[1] if len(parts) >= 2 else node_name

            is_system = mode == "system" or "system" in pool_label.lower() or "systempool" in node_name.lower()
            runtime_label = "Kubernetes (System Node)" if is_system else "Kubernetes (User Node)"
            pool_clean = pool_label.replace("_", " ").title()
            display_name = f"Node {pool_clean}"

            os_image = node.status.node_info.os_image if node.status.node_info else None

            nodes_res.append(
                ObservedResource(
                    id=f"k8s:node:{node_name}",
                    name=display_name,
                    kind="node",
                    status=status,
                    runtime=runtime_label,
                    uptime=_uptime(created),
                    cpu_percent=cpu_percent,
                    memory_percent=mem_percent,
                    memory_mb=mem_used_mb,
                    memory_limit_mb=alloc_mem_mb,
                    restart_count=0,
                    health="Healthy" if is_ready else "Degraded",
                    start_time=created,
                    container_name=node_name,
                    image_version=os_image,
                    cpu_cores=alloc_cores,
                )
            )
        return nodes_res

    def collect(self) -> list[ObservedResource]:
        resources = []
        try:
            core_v1 = self._client.core()
            pods = core_v1.list_namespaced_pod(self._namespace).items
        except Exception:
            return resources

        pod_metrics = self._fetch_pod_metrics()

        for pod in pods:
            name = pod.metadata.name or ""
            labels = pod.metadata.labels or {}
            
            # Identify specific service/component name
            component = labels.get("app.kubernetes.io/component")
            if not component:
                runtime_type = labels.get("compassx/runtime-type")
                runtime_id = labels.get("compassx/runtime-id") or labels.get("compassx/job")
                if runtime_type or runtime_id:
                    component = f"{runtime_type or 'compute'}-{runtime_id}"
                else:
                    component = labels.get("app.kubernetes.io/name") or labels.get("app") or name

            if component == "compassx":
                parts = name.split("-")
                if len(parts) >= 2 and parts[0] == "compassx":
                    component = parts[1]

            service = component

            if name.endswith("-init") or labels.get("job-name"):
                continue
            phase = pod.status.phase or "Unknown"
            started = pod.status.start_time
            if started and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)

            container_statuses = pod.status.container_statuses or []
            restarts = sum(cs.restart_count for cs in container_statuses)
            all_ready = bool(container_statuses and all(cs.ready for cs in container_statuses))
            health = "Healthy" if (phase == "Running" and all_ready) else phase
            image = container_statuses[0].image if container_statuses else None

            # Calculate metrics
            m = pod_metrics.get(name, {})
            cpu_percent = m.get("cpu_percent", 0.0)
            memory_mb = m.get("memory_mb", 0.0)
            memory_bytes = m.get("memory_bytes", 0.0)

            # Check memory limits from pod spec
            total_limit_bytes = 0.0
            for c_spec in pod.spec.containers:
                res = c_spec.resources
                if res and res.limits:
                    total_limit_bytes += _parse_k8s_memory_bytes(res.limits.get("memory"))

            memory_limit_mb = round(total_limit_bytes / (1024.0 * 1024.0), 2) if total_limit_bytes > 0 else 0.0
            memory_percent = (
                round(memory_bytes / total_limit_bytes * 100.0, 2)
                if total_limit_bytes > 0 and memory_bytes > 0
                else 0.0
            )

            resources.append(
                ObservedResource(
                    id=f"k8s:{service}",
                    name=service.replace("-", " ").title(),
                    kind="service",
                    status=phase.title(),
                    runtime="Kubernetes",
                    uptime=_uptime(started),
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_mb=memory_mb,
                    memory_limit_mb=memory_limit_mb,
                    restart_count=restarts,
                    health=health.title(),
                    start_time=started,
                    container_name=name,
                    image_version=image,
                )
            )
        all_items = resources + self._collect_nodes()
        return sorted(all_items, key=lambda item: (item.kind != "node", item.name))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
