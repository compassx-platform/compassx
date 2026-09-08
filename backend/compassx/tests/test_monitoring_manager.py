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
    assert [point.value for point in series.points] == [18.62]
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


def test_build_collectors_local_dev_only_docker(tmp_path, monkeypatch):
    import unittest.mock as mock
    from compassx.monitoring.collectors import DockerComposeCollector, HostCollector, LocalProcessCollector
    monkeypatch.setattr("docker.from_env", lambda **kw: mock.MagicMock())
    profile = load_profile("local-dev")
    collectors = MonitoringResourceManager._build_collectors(profile, tmp_path)
    types = [type(c) for c in collectors]
    assert DockerComposeCollector in types
    assert HostCollector not in types
    assert LocalProcessCollector not in types


def test_build_collectors_kubernetes_profile(tmp_path):
    from compassx.monitoring.collectors import KubernetesCollector
    profile = load_profile("kubernetes-local")
    collectors = MonitoringResourceManager._build_collectors(profile, tmp_path)
    types = [type(c) for c in collectors]
    assert KubernetesCollector in types


def test_docker_compose_collector_sample_container_handles_uncached_and_limits():
    from unittest.mock import MagicMock
    from compassx.monitoring.collectors import DockerComposeCollector

    mock_client = MagicMock()
    collector = DockerComposeCollector("test-project", client=mock_client)

    # 1. Running container with no cached stats yet (should not raise UnboundLocalError)
    mock_container = MagicMock()
    mock_container.id = "c1"
    mock_container.name = "test-postgres"
    mock_container.status = "running"
    mock_container.labels = {"com.docker.compose.service": "postgres"}
    mock_container.attrs = {
        "State": {"Status": "running", "Health": {"Status": "healthy"}},
        "Config": {"Image": "postgres:15"},
        "HostConfig": {"Memory": 0},
        "RestartCount": 0,
    }

    resource = collector._sample_container(mock_container)
    assert resource is not None
    assert resource.id == "docker:postgres"
    assert resource.memory_limit_mb == 0.0
    assert resource.memory_mb == 0.0

    # 2. Running container with cached stats and explicit memory limit
    collector._cached_stats["c2"] = (
        100.0,
        {
            "cpu_stats": {},
            "precpu_stats": {},
            "memory_stats": {"usage": 50 * 1024 * 1024, "limit": 1000 * 1024 * 1024},
        },
        99.0,
        {"cpu_stats": {}, "precpu_stats": {}, "memory_stats": {}},
    )
    mock_container_with_limit = MagicMock()
    mock_container_with_limit.id = "c2"
    mock_container_with_limit.name = "test-redis"
    mock_container_with_limit.status = "running"
    mock_container_with_limit.labels = {"com.docker.compose.service": "redis"}
    mock_container_with_limit.attrs = {
        "State": {"Status": "running", "Health": {"Status": "healthy"}},
        "Config": {"Image": "redis:7"},
        "HostConfig": {"Memory": 256 * 1024 * 1024},  # 256 MB explicit limit
        "RestartCount": 0,
    }

    resource_limit = collector._sample_container(mock_container_with_limit)
    assert resource_limit is not None
    assert resource_limit.id == "docker:redis"
    assert resource_limit.memory_limit_mb == 256.0
    assert resource_limit.memory_mb == 50.0
    assert resource_limit.memory_percent == round(50.0 / 256.0 * 100, 2)
