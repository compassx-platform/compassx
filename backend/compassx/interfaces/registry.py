from __future__ import annotations

from abc import ABC, abstractmethod

from compassx.models import ServiceEndpoint, ServiceMode


class ServiceRegistry(ABC):
    """Resolves endpoints of long-running platform services.

    Discovery only — never starts, stops, or provisions anything.
    """

    @abstractmethod
    def get_service(self, name: str) -> ServiceEndpoint:
        """Return the endpoint for a service in its configured mode.

        Raises ServiceNotFoundError if the service or mode is unknown.
        """

    @abstractmethod
    def get_mode(self, name: str) -> ServiceMode:
        """Return the deployment mode the service is running in."""

    @abstractmethod
    def list_services(self) -> list[str]:
        """Return the names of all known services."""

    def get_url(self, name: str) -> str:
        return self.get_service(name).base_url
