from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class Resource(BaseModel):
    id: str
    name: str
    kind: Literal["platform", "node", "service"]
    status: str
    runtime: str
    uptime: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    memory_limit_mb: float = 0
    disk_percent: float
    network_in_kbps: float
    network_out_kbps: float
    restart_count: int = 0
    health: str = "Healthy"
    start_time: datetime | None = None
    container_name: str | None = None
    image_version: str | None = None


class Overview(BaseModel):
    total_nodes: int
    total_services: int
    running_services: int
    cpu_utilization: float
    memory_utilization: float
    network_throughput_kbps: float
    runtime: str
    prometheus_connected: bool
    collected_at: datetime


class TimeseriesResponse(BaseModel):
    resource_type: Literal["platform", "node", "service"]
    resource_id: str
    metric: str
    unit: str
    points: list[MetricPoint] = Field(default_factory=list)


class NamedTimeseries(BaseModel):
    resource_id: str
    name: str
    status: str
    points: list[MetricPoint] = Field(default_factory=list)


class GroupedTimeseriesResponse(BaseModel):
    metric: str
    unit: str
    series: list[NamedTimeseries] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    prometheus: str
    runtime: str
    message: str
