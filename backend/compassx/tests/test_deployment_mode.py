import os
from pathlib import Path

import pytest

from compassx.launchers.docker_compose import _to_compose_services, images_for_services
from compassx.models import PlatformError, ServiceMode
from compassx.platform_manager import PlatformManager
from compassx.registry.deployment_mode import (
    apply_mode_environment,
    load_deployment_mode,
    resolve_mode_name,
)
from compassx.registry.profile import DeploymentProfile, ServiceProfileEntry
from compassx.tests.fakes import FakeLauncher
from compassx.tests.test_platform_manager import AlwaysHealthy


def _profile() -> DeploymentProfile:
    names = ["postgres", "redis", "minio", "airflow", "backend", "frontend"]
    return DeploymentProfile(
        name="test",
        default_mode=ServiceMode.DOCKER,
        services={name: ServiceProfileEntry(mode=ServiceMode.DOCKER) for name in names},
        compute_driver="docker",
        compute_overrides={},
        compose_file="deployments/docker-compose/docker-compose.yml",
        compose_project="compassx",
        startup_order=names,
        required_healthy=names,
    )


def test_app_mode_is_the_small_platform():
    mode = load_deployment_mode("app")
    assert mode.includes("postgres")
    assert mode.includes("redis")
    assert mode.includes("backend")
    assert mode.includes("frontend")
    assert not mode.includes("minio")
    assert not mode.includes("airflow")
    assert not mode.includes("enterprise-gateway")
    assert mode.env["STORAGE_BACKEND"] == "local"
    assert mode.compose_files == ("deployments/docker-compose/docker-compose.app.yml",)


def test_full_mode_includes_every_service():
    mode = load_deployment_mode("full")
    assert mode.services is None
    assert mode.includes("minio")
    assert mode.includes("airflow")
    assert mode.filter(["postgres", "minio"]) == ["postgres", "minio"]


def test_unknown_mode_fails():
    with pytest.raises(PlatformError, match="not defined"):
        load_deployment_mode("tiny")


def test_resolve_prefers_explicit_then_env_then_marker(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("COMPASSX_PLATFORM_MODE", raising=False)
    assert resolve_mode_name(repo_root=tmp_path) == "full"

    marker = tmp_path / ".compassx" / "active-mode"
    marker.parent.mkdir(parents=True)
    marker.write_text("app\n", encoding="utf-8")
    assert resolve_mode_name(repo_root=tmp_path) == "app"

    monkeypatch.setenv("COMPASSX_PLATFORM_MODE", "full")
    assert resolve_mode_name(repo_root=tmp_path) == "full"
    assert resolve_mode_name("app", repo_root=tmp_path) == "app"


def test_apply_mode_environment_sets_local_storage(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "minio")
    monkeypatch.setenv("COMPASSX_PLATFORM_MODE", "full")
    apply_mode_environment(load_deployment_mode("app"))
    assert os.environ["COMPASSX_PLATFORM_MODE"] == "app"
    assert os.environ["STORAGE_BACKEND"] == "local"


async def test_platform_manager_app_mode_skips_heavy_services():
    docker = FakeLauncher()
    mode = load_deployment_mode("app")
    manager = PlatformManager(
        _profile(),
        {ServiceMode.DOCKER: docker},
        AlwaysHealthy(),
        deployment_mode=mode,
    )
    status = await manager.up(wait_healthy=False)
    assert docker.started == ["postgres", "redis", "backend", "frontend"]
    assert status.mode == "app"


async def test_platform_manager_rejects_service_outside_mode():
    docker = FakeLauncher()
    manager = PlatformManager(
        _profile(),
        {ServiceMode.DOCKER: docker},
        AlwaysHealthy(),
        deployment_mode=load_deployment_mode("app"),
    )
    with pytest.raises(PlatformError, match="minio"):
        await manager.up(["minio"], wait_healthy=False)
    assert docker.started == []


def test_compose_mapping_includes_airflow_and_mlflow_helpers():
    assert _to_compose_services(["airflow"]) == [
        "jobs-runner-image",
        "airflow-init",
        "airflow-webserver",
        "airflow-scheduler",
    ]
    assert _to_compose_services(["mlflow"]) == ["mlflow-init", "mlflow"]
    assert _to_compose_services(["postgres", "redis"]) == ["postgres", "redis"]


def test_app_services_do_not_need_custom_images():
    assert images_for_services(["postgres", "redis", "backend", "frontend"]) == []


def test_full_services_request_gateway_and_runner_images():
    tags = [tag for tag, _dockerfile, _estimate in images_for_services(["airflow", "enterprise-gateway"])]
    assert "compassx-enterprise-gateway:latest" in tags
    assert "compassx-airflow-notebook-runner:latest" in tags
