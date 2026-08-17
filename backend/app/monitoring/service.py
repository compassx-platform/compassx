from datetime import datetime, timezone

from app.monitoring.schemas import (
    GroupedTimeseriesResponse,
    MetricPoint,
    NamedTimeseries,
    Overview,
    Resource,
    TimeseriesResponse,
)


class MonitoringService:
    """Application facade over the profile-aware monitoring resource manager."""

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def resources(self, kind: str | None = None) -> list[Resource]:
        return [
            Resource.model_validate(item, from_attributes=True)
            for item in self.resource_manager.resources(kind)
        ]

    def overview(self) -> Overview:
        all_resources = self.resources()
        platforms = [item for item in all_resources if item.kind == "platform"]
        nodes = [item for item in all_resources if item.kind == "node"]
        services = [item for item in all_resources if item.kind == "service"]
        aggregate_resources = platforms or nodes or services
        return Overview(
            total_nodes=len(nodes),
            total_services=len(services),
            running_services=sum(item.status.lower() in {"healthy", "running"} for item in services),
            cpu_utilization=round(
                sum(item.cpu_percent for item in aggregate_resources)
                / max(len(aggregate_resources), 1),
                1,
            ),
            memory_utilization=round(
                sum(item.memory_percent for item in aggregate_resources)
                / max(len(aggregate_resources), 1),
                1,
            ),
            network_throughput_kbps=round(
                sum(
                    item.network_in_kbps + item.network_out_kbps
                    for item in aggregate_resources
                ),
                1,
            ),
            runtime=self.resource_manager.source,
            prometheus_connected=self.resource_manager.prometheus_connected,
            collected_at=datetime.now(timezone.utc),
        )

    def timeseries(
        self, resource_type: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> TimeseriesResponse:
        observed = self.resource_manager.timeseries(
            resource_type, resource_id, metric, start, end, step
        )
        return TimeseriesResponse.model_validate(observed, from_attributes=True)

    def service_timeseries(
        self, metric: str, start: int, end: int, step: int
    ) -> GroupedTimeseriesResponse:
        services = self.resources("service")
        series = []
        unit = ""
        for resource in services:
            observed = self.resource_manager.timeseries(
                "service", resource.id, metric, start, end, step
            )
            unit = observed.unit
            series.append(
                NamedTimeseries(
                    resource_id=resource.id,
                    name=resource.name,
                    status=resource.status,
                    points=[
                        MetricPoint.model_validate(point, from_attributes=True)
                        for point in observed.points
                    ],
                )
            )
        return GroupedTimeseriesResponse(metric=metric, unit=unit, series=series)
