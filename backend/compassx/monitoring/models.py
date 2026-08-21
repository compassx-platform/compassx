from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MetricPoint:
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class ObservedResource:
    id: str
    name: str
    kind: str
    status: str
    runtime: str
    uptime: str
    cpu_percent: float = 0
    memory_percent: float = 0
    memory_mb: float = 0
    memory_limit_mb: float = 0
    disk_percent: float = 0
    network_in_kbps: float = 0
    network_out_kbps: float = 0
    disk_read_kbps: float = 0
    disk_write_kbps: float = 0
    restart_count: int = 0
    health: str = "Unknown"
    start_time: datetime | None = None
    container_name: str | None = None
    image_version: str | None = None


@dataclass(frozen=True)
class Timeseries:
    resource_type: str
    resource_id: str
    metric: str
    unit: str
    points: list[MetricPoint] = field(default_factory=list)
