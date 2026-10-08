"""Factory to instantiate the appropriate Sandbox Driver according to deployment mode."""
import logging
from typing import Optional

from app.sandbox.interfaces import BaseSandboxDriver
from app.sandbox.drivers.docker_driver import DockerSandboxDriver
from app.sandbox.drivers.k8s_driver import KubernetesSandboxDriver
from app.sandbox.drivers.local_driver import LocalSandboxDriver
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)


class SandboxDriverFactory:
    """Factory resolving runtime sandbox driver."""

    def __init__(self):
        self._drivers = {}

    def get_driver(self, mode: Optional[str] = None) -> BaseSandboxDriver:
        """Resolve driver instance for given mode or active platform mode."""
        active_mode = (mode or ingress_service.get_active_mode()).lower().strip()
        if active_mode in ("k8s", "kubernetes"):
            driver_key = "kubernetes"
            if driver_key not in self._drivers:
                self._drivers[driver_key] = KubernetesSandboxDriver()
            return self._drivers[driver_key]
        elif active_mode == "docker":
            driver_key = "docker"
            if driver_key not in self._drivers:
                self._drivers[driver_key] = DockerSandboxDriver()
            return self._drivers[driver_key]
        else:
            driver_key = "local"
            if driver_key not in self._drivers:
                self._drivers[driver_key] = LocalSandboxDriver()
            return self._drivers[driver_key]


sandbox_driver_factory = SandboxDriverFactory()
