from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from compassx.interfaces.registry import ServiceRegistry
from compassx.models import ServiceEndpoint, ServiceMode, ServiceNotFoundError

SERVICES_FILE = Path(__file__).resolve().parent.parent / "services.yaml"


def load_service_definitions(path: Path | None = None) -> dict[str, Any]:
    """Load the services × modes endpoint definitions from YAML."""
    with open(path or SERVICES_FILE, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("services") or {}


def _env_override(service: str, mode: ServiceMode, key: str) -> str | None:
    # COMPASSX_SERVICE_<NAME>_<MODE>_<KEY>, dashes -> underscores
    name = service.upper().replace("-", "_")
    return os.environ.get(f"COMPASSX_SERVICE_{name}_{mode.value.upper()}_{key.upper()}")


class YamlServiceRegistry(ServiceRegistry):
    """ServiceRegistry backed by services.yaml + a deployment profile.

    Each service resolves independently based on its per-service mode,
    so hybrid deployments (backend local, airflow k8s, minio docker)
    work without special cases.
    """

    def __init__(
        self,
        definitions: Mapping[str, Any],
        service_modes: Mapping[str, ServiceMode],
        default_mode: ServiceMode = ServiceMode.LOCAL,
        perspective: str = "container",
    ) -> None:
        """perspective: where the *caller* runs.

        - "container": caller shares the service network (docker network /
          k8s cluster) -> docker/k8s services resolve to network hostnames.
        - "host": caller is a native host process (local-dev backend) ->
          docker/k8s services resolve via their `local` entry (published
          ports / kubectl port-forwards on localhost).
        """
        self._definitions = dict(definitions)
        self._service_modes = dict(service_modes)
        self._default_mode = default_mode
        self._perspective = perspective

    @classmethod
    def from_files(
        cls,
        profile: "DeploymentProfile",  # noqa: F821 - avoid circular import at runtime
        services_path: Path | None = None,
        perspective: str | None = None,
    ) -> "YamlServiceRegistry":
        if perspective is None:
            # If any service (typically the backend) runs natively, callers
            # importing this registry are host processes.
            backend_mode = profile.mode_for("backend")
            perspective = "host" if backend_mode == ServiceMode.LOCAL else "container"
        return cls(
            definitions=load_service_definitions(services_path),
            service_modes=profile.service_modes(),
            default_mode=profile.default_mode,
            perspective=perspective,
        )

    def get_mode(self, name: str) -> ServiceMode:
        if name not in self._definitions:
            raise ServiceNotFoundError(f"Unknown service '{name}'")
        return self._service_modes.get(name, self._default_mode)

    def get_service(self, name: str) -> ServiceEndpoint:
        definition = self._definitions.get(name)
        if definition is None:
            available = ", ".join(sorted(self._definitions)) or "<none>"
            raise ServiceNotFoundError(
                f"Unknown service '{name}'. Known services: {available}"
            )
        mode = self.get_mode(name)
        # Host processes reach containerized services via localhost
        # (published ports / port-forwards), not network hostnames.
        lookup_mode = mode.value
        if self._perspective == "host" and mode in (
            ServiceMode.DOCKER,
            ServiceMode.KUBERNETES,
        ):
            lookup_mode = ServiceMode.LOCAL.value
        entry = definition.get(lookup_mode) or definition.get(mode.value)
        if entry is None:
            raise ServiceNotFoundError(
                f"Service '{name}' has no endpoint defined for mode '{mode.value}'"
            )
        host = _env_override(name, mode, "host") or entry["host"]
        port_override = _env_override(name, mode, "port")
        port = int(port_override) if port_override else int(entry["port"])
        protocol = entry.get("protocol", "http")
        return ServiceEndpoint(host=host, port=port, protocol=protocol)

    def list_services(self) -> list[str]:
        return sorted(self._definitions)
