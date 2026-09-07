"""Factory for resolving runtime drivers dynamically based on deployment mode (SOLID / DIP)."""
import logging
from typing import Optional

from app.services.drivers.base import BaseAppDriver, BaseDevDriver
from app.services.drivers.docker_driver import DockerAppDriver, DockerDevDriver
from app.services.drivers.kubernetes_driver import KubernetesAppDriver, KubernetesDevDriver
from app.services.drivers.local_driver import LocalAppDriver, LocalDevDriver
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)


class DriverFactory:
    """Instantiates appropriate runtime drivers according to the active mode."""

    @staticmethod
    def get_app_driver(mode: Optional[str] = None) -> BaseAppDriver:
        active_mode = (mode or ingress_service.get_active_mode()).lower()
        if active_mode == "kubernetes":
            return KubernetesAppDriver()
        elif active_mode == "docker":
            return DockerAppDriver()
        else:
            return LocalAppDriver()

    @staticmethod
    def get_dev_driver(mode: Optional[str] = None) -> BaseDevDriver:
        active_mode = (mode or ingress_service.get_active_mode()).lower()
        if active_mode == "kubernetes":
            return KubernetesDevDriver()
        elif active_mode == "docker":
            return DockerDevDriver()
        else:
            return LocalDevDriver()


driver_factory = DriverFactory()
