from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from compassx.models import PlatformError, ServiceMode

PROFILE_ENV_VAR = "COMPASSX_PLATFORM_PROFILE"
DEFAULT_PROFILE = "local-dev"
PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


@dataclass
class ServiceProfileEntry:
    mode: ServiceMode
    command: list[str] = field(default_factory=list)
    cwd: str = ""
    windowed: bool = False  # Windows: open a new CMD window instead of logging to file


@dataclass
class DeploymentProfile:
    """Parsed deployment profile: where each platform service executes."""

    name: str
    default_mode: ServiceMode
    services: dict[str, ServiceProfileEntry]
    compute_driver: str
    compute_overrides: dict[str, str]
    compose_file: str
    compose_project: str
    docker_ensure_images: bool = False
    k8s_namespace: str = "compassx-jobs"
    k8s_ensure_images: bool = False
    k8s_ensure_rbac: bool = False
    k8s_port_forwards: bool = False
    startup_order: list[str] = field(default_factory=list)
    required_healthy: list[str] = field(default_factory=list)
    k8s_exposed_services: list[str] = field(default_factory=list)
    """Services to expose via kubectl port-forward from the host machine.

    Only services that the *developer's browser or CLI tools* need to reach
    directly should be listed here.  In kubernetes mode all inter-service
    communication goes through cluster-internal DNS — port-forwards are only
    for human access (browser, psql, curl …).
    """
    k8s_external_services: list[str] = field(default_factory=list)
    """Services whose infrastructure is provided externally (not deployed by the launcher).

    When a service is listed here:
    - Its Kubernetes manifest is NOT applied (no in-cluster pod/StatefulSet created).
    - The user is responsible for providing connection details via the
      `compassx-backend-secrets` Kubernetes Secret (see k8s/secrets/README.md).
    - The service registry still resolves it — point it at your external host
      using the COMPASSX_SERVICE_<NAME>_KUBERNETES_HOST / _PORT env-vars, or
      just override PG_HOST / PG_PORT directly in the Secret.

    Example — bring your own postgres:
        kubernetes:
          external_services: [postgres]
    """
    raw: dict[str, Any] = field(default_factory=dict)

    def mode_for(self, service: str) -> ServiceMode:
        entry = self.services.get(service)
        return entry.mode if entry else self.default_mode

    def service_modes(self) -> dict[str, ServiceMode]:
        return {name: entry.mode for name, entry in self.services.items()}

    def driver_for_runtime(self, runtime_type: str) -> str:
        return self.compute_overrides.get(runtime_type, self.compute_driver)


def _parse_profile(name: str, data: dict[str, Any]) -> DeploymentProfile:
    defaults = data.get("defaults") or {}
    default_mode = ServiceMode(defaults.get("mode", "docker"))

    services: dict[str, ServiceProfileEntry] = {}
    for svc_name, svc in (data.get("services") or {}).items():
        svc = svc or {}
        services[svc_name] = ServiceProfileEntry(
            mode=ServiceMode(svc.get("mode", default_mode.value)),
            command=list(svc.get("command") or []),
            cwd=svc.get("cwd", ""),
            windowed=bool(svc.get("windowed", False)),
        )

    compute = data.get("compute") or {}
    docker = data.get("docker") or {}
    k8s = data.get("kubernetes") or {}

    return DeploymentProfile(
        name=data.get("profile", name),
        default_mode=default_mode,
        services=services,
        compute_driver=compute.get("driver", "kubernetes"),
        compute_overrides=dict(compute.get("overrides") or {}),
        compose_file=docker.get("compose_file", "deployments/docker-compose/docker-compose.yml"),
        compose_project=docker.get("project_name", "compassx"),
        docker_ensure_images=bool(docker.get("ensure_images", False)),
        k8s_namespace=k8s.get("namespace", "compassx-jobs"),
        k8s_ensure_images=bool(k8s.get("ensure_images", False)),
        k8s_ensure_rbac=bool(k8s.get("ensure_rbac", False)),
        k8s_port_forwards=bool(k8s.get("port_forwards", False)),
        k8s_exposed_services=list(k8s.get("exposed_services") or []),
        k8s_external_services=list(k8s.get("external_services") or []),
        startup_order=list(data.get("startup_order") or []),
        required_healthy=list(data.get("required_healthy") or []),
        raw=data,
    )



def list_profiles(profiles_dir: Path | None = None) -> list[str]:
    directory = profiles_dir or PROFILES_DIR
    return sorted(p.stem for p in directory.glob("*.yaml"))


def load_profile(
    name: str | None = None, profiles_dir: Path | None = None
) -> DeploymentProfile:
    """Load a deployment profile by name.

    Resolution order: explicit arg > COMPASSX_PLATFORM_PROFILE env > default.
    """
    resolved = name or os.environ.get(PROFILE_ENV_VAR) or DEFAULT_PROFILE
    directory = profiles_dir or PROFILES_DIR
    path = directory / f"{resolved}.yaml"
    if not path.exists():
        available = ", ".join(list_profiles(directory)) or "<none>"
        raise PlatformError(
            f"Deployment profile '{resolved}' not found at {path}. Available: {available}"
        )
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return _parse_profile(resolved, data)
