from dataclasses import replace
from datetime import datetime, timezone

from compassx.monitoring.collectors import ResourceCollector
from compassx.monitoring.manager import MonitoringResourceManager
from compassx.monitoring.models import ObservedResource
from compassx.registry import load_profile


class MutableCollector(ResourceCollector):
    def __init__(self, resource: ObservedResource):
        self.resource = resource

    def collect(self) -> list[ObservedResource]:
        return [self.resource]


def test_manager_records_only_observed_values(tmp_path):
    collector = MutableCollector(
        ObservedResource(
            id="process:backend",
            name="Backend",
            kind="service",
            status="Running",
            runtime="Local process",
            uptime="1h 2m",
            cpu_percent=12.5,
            memory_mb=256,
            start_time=datetime.now(timezone.utc),
        )
    )
    manager = MonitoringResourceManager(
        load_profile("local-dev"), tmp_path, collectors=[collector], cache_seconds=0
    )

    assert manager.resources("service")[0].cpu_percent == 12.5
    collector.resource = replace(collector.resource, cpu_percent=24.75)
    manager.resources()

    series = manager.timeseries(
        "service", "process:backend", "cpu", 0, 9_999_999_999, 300
    )
    assert [point.value for point in series.points] == [20.67]
    assert series.unit == "%"


def test_manager_filters_resource_kind(tmp_path):
    collector = MutableCollector(
        ObservedResource(
            id="local-host",
            name="Local host",
            kind="node",
            status="Healthy",
            runtime="Local",
            uptime="1d 0h",
        )
    )
    manager = MonitoringResourceManager(
        load_profile("local-dev"), tmp_path, collectors=[collector]
    )

    assert manager.resources("service") == []
    assert [resource.id for resource in manager.resources("node")] == ["local-host"]


def test_manager_builds_platform_health_from_services(tmp_path):
    class ServiceCollector(ResourceCollector):
        def collect(self) -> list[ObservedResource]:
            return [
                ObservedResource(
                    id="process:backend", name="Backend", kind="service",
                    status="Running", health="Healthy", runtime="Local", uptime="1h",
                    cpu_percent=15, memory_percent=10, memory_mb=200,
                ),
                ObservedResource(
                    id="docker:redis", name="Redis", kind="service",
                    status="Exited", health="Stopped", runtime="Docker", uptime="-",
                ),
            ]

    manager = MonitoringResourceManager(
        load_profile("local-dev"), tmp_path, collectors=[ServiceCollector()]
    )

    platform = manager.resources("platform")[0]
    assert platform.id == "platform:local-dev"
    assert platform.status == "Degraded"
    assert platform.cpu_percent == 15
    assert platform.memory_mb == 200
