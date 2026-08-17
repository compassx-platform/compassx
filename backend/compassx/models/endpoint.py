from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ServiceMode(str, Enum):
    """Where a platform service executes."""

    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"


@dataclass(frozen=True)
class ServiceEndpoint:
    """Resolved network endpoint for a platform service.

    Deployment-independent: callers never see whether the host is a
    localhost port-forward, a docker-compose hostname, or a Kubernetes
    Service DNS name.
    """

    host: str
    port: int
    protocol: str = "http"

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def address(self) -> str:
        """host:port pair without protocol (e.g. for S3/DB clients)."""
        return f"{self.host}:{self.port}"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.base_url
