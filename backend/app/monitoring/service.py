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

        if nodes:
            total_used_mb = sum(n.memory_mb for n in nodes)
            total_limit_mb = sum(n.memory_limit_mb for n in nodes if n.memory_limit_mb > 0)
            mem_util = round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0
            cpu_util = round(sum(n.cpu_percent for n in nodes) / max(len(nodes), 1), 1)
            net_throughput = round(sum(n.network_in_kbps + n.network_out_kbps for n in nodes), 1)
        elif platforms:
            plat = platforms[0]
            total_used_mb = plat.memory_mb
            total_limit_mb = plat.memory_limit_mb or sum(s.memory_limit_mb for s in services if s.memory_limit_mb > 0) or total_used_mb
            mem_util = plat.memory_percent or (round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0)
            cpu_util = plat.cpu_percent
            net_throughput = round(plat.network_in_kbps + plat.network_out_kbps, 1)
        else:
            total_used_mb = sum(s.memory_mb for s in services)
            total_limit_mb = sum(s.memory_limit_mb for s in services if s.memory_limit_mb > 0) or total_used_mb
            mem_util = round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0
            cpu_util = round(sum(s.cpu_percent for s in services) / max(len(services), 1), 1)
            net_throughput = round(sum(s.network_in_kbps + s.network_out_kbps for s in services), 1)

        import psutil, os
        node_cores = sum(int(getattr(n, "cpu_cores", 0)) for n in nodes if getattr(n, "cpu_cores", 0) > 0)
        total_cores = node_cores or psutil.cpu_count(logical=True) or os.cpu_count() or 1
        total_nodes = len(nodes) or (1 if platforms or services else 0)

        return Overview(
            total_nodes=total_nodes,
            total_cores=int(total_cores),
            total_services=len(services),
            running_services=sum(item.status.lower() in {"healthy", "running"} for item in services),
            cpu_utilization=cpu_util,
            memory_utilization=mem_util,
            network_throughput_kbps=net_throughput,
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
        current_service_map = {s.id: s for s in services}
        unit, grouped = self.resource_manager.timeseries_grouped(metric, start, end, step)
        series = []
        seen_ids = set()

        for resource in services:
            points = grouped.get(resource.id, [])
            seen_ids.add(resource.id)
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

        # Include historical services/pods present in Prometheus but now stopped
        for resource_id, points in grouped.items():
            if resource_id not in seen_ids:
                if resource_id.startswith("k8s:node:") or resource_id.startswith("platform:"):
                    continue
                clean_name = resource_id.replace("docker:", "").replace("k8s:pod:", "").replace("compassx-", "")
                series.append(
                    NamedTimeseries(
                        resource_id=resource_id,
                        name=f"{clean_name} (Stopped)",
                        status="Terminated",
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

            curr = current_node_map.get(resource_id)
            if curr:
                name = curr.name
                status = curr.status
            else:
                parts = resource_id.replace("k8s:node:", "").split("-")
                pool_name = parts[1] if len(parts) >= 2 else "Node"
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
            for resource in nodes:
                series.append(
                    NamedTimeseries(
                        resource_id=resource.id,
                        name=resource.name,
                        status=resource.status,
                        points=[],
                    )
                )

        return GroupedTimeseriesResponse(metric=metric, unit=unit, series=series)
