"""Base service manager interface."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ServicePhase(str, Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    ERROR = "Error"


@dataclass
class ServiceStatus:
    phase: ServicePhase
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class ServiceResourceUsage:
    cpu_millicores: Optional[int] = None
    memory_mib: Optional[int] = None
    metrics_available: bool = False


class BaseServiceManager:
    """Base class for all CompassX service managers."""

    def start(self) -> ServiceStatus:
        raise NotImplementedError

    def stop(self) -> ServiceStatus:
        raise NotImplementedError

    def restart(self) -> ServiceStatus:
        raise NotImplementedError

    def get_status(self) -> ServiceStatus:
        raise NotImplementedError

    def get_resource_usage(self) -> ServiceResourceUsage:
        raise NotImplementedError
