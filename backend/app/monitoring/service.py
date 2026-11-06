"""Monitoring application facade.

``MonitoringService`` stays importable from ``app.monitoring.service``.
Each method forwards to one application type. The resource manager stays on the instance.
"""
from app.monitoring.history.application.node_timeseries import node_timeseries
from app.monitoring.history.application.service_timeseries import service_timeseries
from app.monitoring.history.application.timeseries import read_timeseries
from app.monitoring.resources.application.list_resources import list_resources
from app.monitoring.resources.application.overview import build_overview
from app.monitoring.schemas import (
    GroupedTimeseriesResponse,
    Overview,
    Resource,
    TimeseriesResponse,
)


class MonitoringService:
    """Application facade over the profile-aware monitoring resource manager."""

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def resources(self, kind: str | None = None) -> list[Resource]:
        return list_resources(self.resource_manager, kind)

    def overview(self) -> Overview:
        return build_overview(self.resource_manager)

    def timeseries(
        self, resource_type: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> TimeseriesResponse:
        return read_timeseries(self.resource_manager, resource_type, resource_id, metric, start, end, step)

    def service_timeseries(
        self, metric: str, start: int, end: int, step: int
    ) -> GroupedTimeseriesResponse:
        return service_timeseries(self.resource_manager, metric, start, end, step)

    def node_timeseries(
        self, metric: str, start: int, end: int, step: int
    ) -> GroupedTimeseriesResponse:
        return node_timeseries(self.resource_manager, metric, start, end, step)
