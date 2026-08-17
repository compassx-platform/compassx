from prometheus_client import CollectorRegistry, Gauge, generate_latest


_FIELDS = {
    "cpu": "cpu_percent",
    "memory": "memory_mb",
    "network_in": "network_in_kbps",
    "network_out": "network_out_kbps",
    "disk_read": "disk_read_kbps",
    "disk_write": "disk_write_kbps",
}


def render_prometheus_metrics(resource_manager) -> bytes:
    """Render current profile resources using a stable, low-cardinality schema."""
    resource_manager.request_refresh()
    registry = CollectorRegistry()
    gauge = Gauge(
        "compassx_resource_metric",
        "Observed CompassX resource metric",
        ("profile", "resource_kind", "resource_id", "metric"),
        registry=registry,
    )
    for resource in resource_manager.resource_snapshot():
        for metric, field in _FIELDS.items():
            gauge.labels(
                profile=resource_manager.source,
                resource_kind=resource.kind,
                resource_id=resource.id,
                metric=metric,
            ).set(float(getattr(resource, field)))
    return generate_latest(registry)
