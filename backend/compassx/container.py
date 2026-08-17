"""Dependency-injection container for the platform layer.

No singletons: the container is instantiated once per process (CLI run
or FastAPI app) and handed around explicitly. Components are created
lazily and cached per-container.
"""

from __future__ import annotations

import logging
import os
from functools import cached_property
from pathlib import Path

from compassx.interfaces.launcher import Launcher
from compassx.models import ServiceMode
from compassx.platform_manager import HealthChecker, PlatformManager
from compassx.registry import DeploymentProfile, YamlServiceRegistry, load_profile

logger = logging.getLogger(__name__)


def _find_repo_root(start: Path | None = None) -> Path:
    """Walk up from backend/ to the repo root (contains backend/ + frontend/)."""
    current = (start or Path(__file__).resolve().parent).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "backend").is_dir() and (candidate / ".git").exists():
            return candidate
    # Fallback: parent of backend/
    return Path(__file__).resolve().parents[2]


class PlatformContainer:
    def __init__(
        self,
        profile_name: str | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._profile_name = profile_name
        self._repo_root = repo_root or _find_repo_root()

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @cached_property
    def profile(self) -> DeploymentProfile:
        profile = load_profile(self._profile_name)
        logger.info("platform: active profile '%s'", profile.name)
        self._set_compassx_env(profile)
        return profile

    @cached_property
    def service_registry(self) -> YamlServiceRegistry:
        """Container-perspective registry — for use inside Kubernetes pods (cluster DNS)."""
        return YamlServiceRegistry.from_files(self.profile)

    @cached_property
    def host_service_registry(self) -> YamlServiceRegistry:
        """Host-perspective registry — for use from the host machine (port-forwards).

        In kubernetes profiles all services are reachable via kubectl port-forward on
        localhost:<port>. The CLI uses this registry for health checks so it doesn't
        try to reach cluster-internal DNS from outside the cluster.
        """
        return YamlServiceRegistry.from_files(self.profile, perspective="host")

    @cached_property
    def health_checker(self) -> HealthChecker:
        """Health checker using host-perspective endpoints (localhost port-forwards).

        Always uses host perspective so `compassx health` and `compassx up --wait`
        work correctly from the developer's machine regardless of where services run.
        """
        return HealthChecker(self.host_service_registry)

    @cached_property
    def launchers(self) -> dict[ServiceMode, Launcher]:
        from compassx.launchers import (
            DockerComposeLauncher,
            KubernetesLauncher,
            LocalProcessLauncher,
        )

        return {
            ServiceMode.LOCAL: LocalProcessLauncher(self.profile, self._repo_root),
            ServiceMode.DOCKER: DockerComposeLauncher(self.profile, self._repo_root),
            ServiceMode.KUBERNETES: KubernetesLauncher(self.profile, self._repo_root),
        }

    @cached_property
    def platform_manager(self) -> PlatformManager:
        return PlatformManager(self.profile, self.launchers, self.health_checker)

    @cached_property
    def monitoring_resource_manager(self):
        from compassx.monitoring import (
            MonitoringResourceManager,
            PrometheusMetricRepository,
            SqliteMetricRepository,
        )

        fallback = SqliteMetricRepository(
            self._repo_root / ".compassx" / "monitoring" / "metrics.db"
        )
        repository = PrometheusMetricRepository(
            self.service_registry.get_url("prometheus"), fallback
        )
        return MonitoringResourceManager(
            self.profile, self._repo_root, repository=repository
        )

    # ── runtime side (used by the backend) ───────────────────────────────

    @cached_property
    def driver_registry(self):
        from compassx.runtime import DriverRegistry

        registry = DriverRegistry()
        registry.register("local", self._make_local_driver)
        registry.register("docker", self._make_docker_driver)
        registry.register("kubernetes", self._make_kubernetes_driver)
        return registry

    def _make_local_driver(self):
        from compassx.drivers.local import LocalDriver

        return LocalDriver(state_dir=self._repo_root / ".compassx" / "runtimes")

    def _make_docker_driver(self):
        from compassx.drivers.docker import DockerDriver

        # Attach runtimes to the compose network so they reach platform services.
        network = f"{self.profile.compose_project}_default"
        return DockerDriver(network=network)

    def _make_kubernetes_driver(self):
        from compassx.drivers.k8s_client import K8sApiClient
        from compassx.drivers.kubernetes import KubernetesDriver

        skip_ssl = os.environ.get("SKIP_K8S_SSL_VERIFY", "").lower() in ("1", "true", "yes")
        client = K8sApiClient(skip_ssl_verify=skip_ssl)
        return KubernetesDriver(client, namespace=self.profile.k8s_namespace)

    def _set_compassx_env(self, profile: DeploymentProfile) -> None:
        """Sync the shared COMPASSX_ENV setting with the active profile.

        Local-dev/docker and kubernetes-local should behave as "local".
        kubernetes-cloud should behave as "cloud".
        """
        from app.compute.services.config import compute_settings

        compassx_env = "cloud" if profile.name.endswith("-cloud") else "local"
        compute_settings.COMPASSX_ENV = compassx_env
        os.environ["COMPASSX_ENV"] = compassx_env

    def build_runtime_manager(self, repository=None):
        """Build a RuntimeManager. Pass a SqlRuntimeRepository from the
        backend; defaults to in-memory (CLI/tests)."""
        from compassx.runtime import (
            DefaultResourceManager,
            DefaultRuntimeManager,
            InMemoryRuntimeRepository,
            default_spec_builders,
        )

        repository = repository or InMemoryRuntimeRepository()
        # Runtime processes execute inside a container/pod even when the backend
        # itself is native on the host, so inject container-reachable endpoints.
        from compassx.registry import YamlServiceRegistry

        runtime_registry = YamlServiceRegistry.from_files(
            self.profile, perspective="container"
        )
        minio = runtime_registry.get_service("minio")
        resource_manager = DefaultResourceManager(
            self.driver_registry,
            repository,
            default_driver=self.profile.compute_driver,
        )
        return DefaultRuntimeManager(
            resource_manager,
            default_spec_builders(
                minio_endpoint=minio.address,
                minio_access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
                minio_secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
                registry_prefix=os.environ.get("COMPUTE_REGISTRY_PREFIX", ""),
            ),
            repository,
            driver_policy=self.profile.driver_for_runtime,
            namespace=self.profile.k8s_namespace,
            env=("cloud" if self.profile.name.endswith("-cloud") else "local"),
        )
