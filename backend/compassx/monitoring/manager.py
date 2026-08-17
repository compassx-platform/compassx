from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread

from compassx.models import ServiceMode
from compassx.monitoring.collectors import (
    DockerComposeCollector,
    HostCollector,
    LocalProcessCollector,
    ResourceCollector,
)
from compassx.monitoring.models import ObservedResource, Timeseries
from compassx.monitoring.repository import (
    InMemoryMetricRepository,
    MetricRepository,
    MetricSample,
)
from compassx.registry import DeploymentProfile

logger = logging.getLogger(__name__)

_METRICS = {
    "cpu": ("cpu_percent", "%"),
    "memory": ("memory_mb", "MB"),
    "network_in": ("network_in_kbps", "KB/s"),
    "network_out": ("network_out_kbps", "KB/s"),
    "disk_read": ("disk_read_kbps", "KB/s"),
    "disk_write": ("disk_write_kbps", "KB/s"),
}


class MonitoringResourceManager:
    """Profile-aware owner of observed resource data and rolling history."""

    def __init__(
        self,
        profile: DeploymentProfile,
        repo_root: Path,
        *,
        collectors: list[ResourceCollector] | None = None,
        repository: MetricRepository | None = None,
        cache_seconds: float = 1.0,
    ) -> None:
        self.profile = profile
        self._collectors = collectors if collectors is not None else self._build_collectors(profile, repo_root)
        self._repository = repository or InMemoryMetricRepository()
        self._resources: list[ObservedResource] = []
        self._last_collection = 0.0
        self._cache_seconds = cache_seconds
        self._collection_lock = Lock()
        self._refresh_thread: Thread | None = None

    @staticmethod
    def _build_collectors(profile: DeploymentProfile, repo_root: Path) -> list[ResourceCollector]:
        collectors: list[ResourceCollector] = []
        modes = set(profile.service_modes().values()) | {profile.default_mode}
        if ServiceMode.LOCAL in modes:
            collectors.extend([HostCollector(), LocalProcessCollector(profile, repo_root)])
        if ServiceMode.DOCKER in modes:
            try:
                collectors.append(DockerComposeCollector(profile.compose_project))
            except Exception as exc:
                logger.warning("Docker monitoring is unavailable: %s", exc)
        return collectors

    @property
    def source(self) -> str:
        return self.profile.name

    @property
    def prometheus_connected(self) -> bool:
        return bool(getattr(self._repository, "connected", False))

    def resources(self, kind: str | None = None) -> list[ObservedResource]:
        with self._collection_lock:
            self._collect_unlocked()
            return [item for item in self._resources if kind is None or item.kind == kind]

    def resource_snapshot(self) -> list[ObservedResource]:
        """Return the last completed sample without waiting on infrastructure."""
        return list(self._resources)

    def request_refresh(self) -> None:
        """Refresh asynchronously so scrape requests are never infrastructure-bound."""
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return
        self._refresh_thread = Thread(
            target=self.resources,
            name="compassx-monitoring-refresh",
            daemon=True,
        )
        self._refresh_thread.start()

    def timeseries(
        self, resource_type: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> Timeseries:
        with self._collection_lock:
            self._collect_unlocked()
            _field, unit = _METRICS[metric]
            points = self._repository.query(
                self.profile.name, resource_id, metric, start, end, step
            )
        return Timeseries(resource_type, resource_id, metric, unit, points)

    def _collect(self) -> None:
        with self._collection_lock:
            self._collect_unlocked()

    def _collect_unlocked(self) -> None:
        now = time.monotonic()
        if self._resources and now - self._last_collection < self._cache_seconds:
            return
        observed: list[ObservedResource] = []
        for collector in self._collectors:
            try:
                observed.extend(collector.collect())
            except Exception as exc:
                logger.warning("Monitoring collector %s failed: %s", type(collector).__name__, exc)
        services = [item for item in observed if item.kind == "service"]
        if services:
            observed.append(self._platform_resource(services))
        self._resources = observed
        self._last_collection = time.monotonic()
        timestamp = datetime.now(timezone.utc)
        samples = []
        for resource in observed:
            for metric, (field, _unit) in _METRICS.items():
                samples.append(
                    MetricSample(
                        profile=self.profile.name,
                        resource_kind=resource.kind,
                        resource_id=resource.id,
                        metric=metric,
                        timestamp=timestamp,
                        value=float(getattr(resource, field)),
                    )
                )
        self._repository.record(samples)

    def _platform_resource(self, services: list[ObservedResource]) -> ObservedResource:
        healthy_states = {"healthy", "running"}
        unhealthy = [
            item for item in services
            if item.status.lower() not in healthy_states
            or item.health.lower() not in healthy_states
        ]
        started = [item.start_time for item in services if item.start_time is not None]
        return ObservedResource(
            id=f"platform:{self.profile.name}",
            name=f"CompassX ({self.profile.name})",
            kind="platform",
            status="Degraded" if unhealthy else "Healthy",
            runtime=self.profile.name,
            uptime="-",
            cpu_percent=round(min(100, sum(item.cpu_percent for item in services)), 2),
            memory_percent=round(min(100, sum(item.memory_percent for item in services)), 2),
            memory_mb=round(sum(item.memory_mb for item in services), 2),
            network_in_kbps=round(sum(item.network_in_kbps for item in services), 2),
            network_out_kbps=round(sum(item.network_out_kbps for item in services), 2),
            disk_read_kbps=round(sum(item.disk_read_kbps for item in services), 2),
            disk_write_kbps=round(sum(item.disk_write_kbps for item in services), 2),
            health="Degraded" if unhealthy else "Healthy",
            start_time=min(started) if started else None,
        )
