from app.monitoring.resources.application.list_resources import list_resources
from app.monitoring.schemas import GroupedTimeseriesResponse, MetricPoint, NamedTimeseries


class ServiceTimeseries:
    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def execute(self, metric: str, start: int, end: int, step: int) -> GroupedTimeseriesResponse:
        services = list_resources(self.resource_manager, "service")
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


def service_timeseries(resource_manager, metric: str, start: int, end: int, step: int) -> GroupedTimeseriesResponse:
    return ServiceTimeseries(resource_manager).execute(metric, start, end, step)
