import pytest

from compassx.models import HealthCheckFailedError, ServiceEndpoint, ServiceMode
from compassx.platform_manager import HealthChecker, PlatformManager
from compassx.registry import YamlServiceRegistry
from compassx.registry.profile import DeploymentProfile, ServiceProfileEntry
from compassx.tests.fakes import FakeLauncher


def make_profile(modes: dict[str, str], order: list[str], required: list[str]):
    return DeploymentProfile(
        name="test",
        default_mode=ServiceMode.DOCKER,
        services={
            name: ServiceProfileEntry(mode=ServiceMode(mode))
            for name, mode in modes.items()
        },
        compute_driver="docker",
        compute_overrides={},
        compose_file="docker/docker-compose.yml",
        compose_project="compassx",
        docker_ensure_images=False,
        k8s_namespace="compassx-jobs",
        k8s_ensure_images=False,
        k8s_ensure_rbac=False,
        k8s_port_forwards=False,
        startup_order=order,
        required_healthy=required,
    )


class AlwaysHealthy(HealthChecker):
    def __init__(self):
        pass

    async def wait_until_healthy(self, services, timeout=120.0, interval=3.0, on_progress=None):
        from compassx.platform_manager.health import HealthReport, ServiceHealth

        return HealthReport(
            services=[ServiceHealth(name=s, healthy=True) for s in services]
        )

    async def check_all(self, services):
        from compassx.platform_manager.health import HealthReport, ServiceHealth

        return HealthReport(
            services=[ServiceHealth(name=s, healthy=True) for s in services]
        )


async def test_up_starts_in_order_grouped_by_launcher():
    docker = FakeLauncher()
    local = FakeLauncher()
    profile = make_profile(
        {"postgres": "docker", "minio": "docker", "backend": "local"},
        order=["postgres", "minio", "backend"],
        required=["postgres"],
    )
    pm = PlatformManager(
        profile,
        {ServiceMode.DOCKER: docker, ServiceMode.LOCAL: local},
        AlwaysHealthy(),
    )
    status = await pm.up()
    assert docker.started == ["postgres", "minio"]
    assert local.started == ["backend"]
    assert status.ready


async def test_down_reverses_order():
    docker = FakeLauncher()
    local = FakeLauncher()
    profile = make_profile(
        {"postgres": "docker", "backend": "local"},
        order=["postgres", "backend"],
        required=[],
    )
    pm = PlatformManager(
        profile,
        {ServiceMode.DOCKER: docker, ServiceMode.LOCAL: local},
        AlwaysHealthy(),
    )
    await pm.down()
    assert local.stopped == ["backend"]
    assert docker.stopped == ["postgres"]


async def test_subset_of_services():
    docker = FakeLauncher()
    profile = make_profile(
        {"postgres": "docker", "minio": "docker"},
        order=["postgres", "minio"],
        required=[],
    )
    pm = PlatformManager(profile, {ServiceMode.DOCKER: docker}, AlwaysHealthy())
    await pm.up(["minio"], wait_healthy=False)
    assert docker.started == ["minio"]


async def test_health_failure_raises_with_root_cause():
    registry = YamlServiceRegistry(
        {"postgres": {"local": {"host": "127.0.0.1", "port": 1}}},
        {"postgres": ServiceMode.LOCAL},
    )
    checker = HealthChecker(registry, connect_timeout=0.3, retries=0)
    with pytest.raises(HealthCheckFailedError) as exc_info:
        await checker.wait_until_healthy(["postgres"], timeout=1.0, interval=0.2)
    message = str(exc_info.value)
    assert "postgres" in message
    # Root-cause guidance present.
    assert "compassx" in message or "refused" in message.lower() or "Timeout" in message


async def test_health_diagnoses_dns_failure():
    registry = YamlServiceRegistry(
        {"minio": {"docker": {"host": "minio-nonexistent-host-xyz", "port": 9000}}},
        {"minio": ServiceMode.DOCKER},
    )
    checker = HealthChecker(registry, connect_timeout=1.0, retries=0)
    result = await checker.check_service("minio")
    assert not result.healthy
    assert result.cause in ("dns", "timeout", "unknown")
    assert result.message  # actionable text present


async def test_health_unregistered_service():
    registry = YamlServiceRegistry({}, {})
    checker = HealthChecker(registry, retries=0)
    result = await checker.check_service("ghost")
    assert not result.healthy
    assert result.cause == "unregistered"
