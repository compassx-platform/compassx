from app.monitoring.resources.application.list_resources import list_resources
from app.monitoring.schemas import GroupedTimeseriesResponse, MetricPoint, NamedTimeseries


class NodeTimeseries:
    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def execute(self, metric: str, start: int, end: int, step: int) -> GroupedTimeseriesResponse:
        nodes = list_resources(self.resource_manager, "node")
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


def node_timeseries(resource_manager, metric: str, start: int, end: int, step: int) -> GroupedTimeseriesResponse:
    return NodeTimeseries(resource_manager).execute(metric, start, end, step)
