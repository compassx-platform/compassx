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
        user_nodes = [
            n for n in nodes
            if "system" not in (n.runtime or "").lower() and "system" not in (n.name or "").lower()
        ]
        display_nodes = user_nodes if user_nodes else nodes
        aggregate_resources = platforms or display_nodes or services

        total_used_mb = sum(item.memory_mb for item in services) or sum(item.memory_mb for item in aggregate_resources)
        total_limit_mb = (
            sum(n.memory_limit_mb for n in display_nodes if n.memory_limit_mb > 0)
            or sum(s.memory_limit_mb for s in services if s.memory_limit_mb > 0)
            or total_used_mb
        )
        mem_util = round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0

        return Overview(
            total_nodes=len(display_nodes),
            total_services=len(services),
            running_services=sum(item.status.lower() in {"healthy", "running"} for item in services),
            cpu_utilization=round(
                sum(item.cpu_percent for item in aggregate_resources)
                / max(len(aggregate_resources), 1),
                1,
            ),
            memory_utilization=mem_util,
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
        unit, grouped = self.resource_manager.timeseries_grouped(metric, start, end, step)
        series = []
        for resource in services:
            points = grouped.get(resource.id, [])
            series.append(
                NamedTimeseries(
                    resource_id=resource.id,
                    name=resource.name,
                    status=resource.status,
                    points=[
                        MetricPoint.model_validate(point, from_attributes=True)
                        for point in points
                    ],
                )
            )
        return GroupedTimeseriesResponse(metric=metric, unit=unit, series=series)

    def node_timeseries(
        self, metric: str, start: int, end: int, step: int
    ) -> GroupedTimeseriesResponse:
        nodes = self.resources("node")
        current_node_map = {n.id: n for n in nodes}
        unit, grouped = self.resource_manager.timeseries_grouped(metric, start, end, step)
        series = []

        for resource_id, points in grouped.items():
            # Check if this resource is a node
            is_node = (
                resource_id.startswith("k8s:node:")
                or resource_id in {"docker-host", "local-host"}
                or resource_id in current_node_map
            )
            if not is_node:
                continue

            # Exclude system pool nodes
            if "systempool" in resource_id.lower() or "system" in resource_id.lower():
                continue

            curr = current_node_map.get(resource_id)
            if curr:
                name = curr.name
                status = curr.status
            else:
                parts = resource_id.replace("k8s:node:", "").split("-")
                pool_name = parts[1] if len(parts) >= 2 else "Userpool"
                name = f"Node {pool_name.replace('_', ' ').title()} (Scaled Down)"
                status = "Terminated"

            series.append(
                NamedTimeseries(
                    resource_id=resource_id,
                    name=name,
                    status=status,
                    points=[
                        MetricPoint.model_validate(point, from_attributes=True)
                        for point in points
                    ],
                )
            )

        # Fallback if no timeseries in Prometheus yet
        if not series:
            user_nodes = [
                n for n in nodes
                if "system" not in (n.runtime or "").lower() and "system" not in (n.name or "").lower()
            ]
            for resource in (user_nodes or nodes):
                series.append(
                    NamedTimeseries(
                        resource_id=resource.id,
                        name=resource.name,
                        status=resource.status,
                        points=[],
                    )
                )

        return GroupedTimeseriesResponse(metric=metric, unit=unit, series=series)
