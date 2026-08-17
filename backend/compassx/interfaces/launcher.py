from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ServiceStatus:
    name: str
    running: bool
    healthy: bool | None = None  # None = unknown / no health check
    detail: str = ""


@dataclass
class LauncherStatus:
    launcher: str
    services: list[ServiceStatus] = field(default_factory=list)

    @property
    def all_running(self) -> bool:
        return bool(self.services) and all(s.running for s in self.services)


class Launcher(ABC):
    """Deployment-specific platform-service lifecycle operations.

    Implementations: LocalProcessLauncher, DockerComposeLauncher,
    KubernetesLauncher. Used only by the Platform Manager.
    """

    name: str = "abstract"

    @abstractmethod
    async def start(self, services: list[str]) -> None: ...

    @abstractmethod
    async def stop(self, services: list[str]) -> None: ...

    @abstractmethod
    async def restart(self, services: list[str]) -> None: ...

    @abstractmethod
    async def status(self, services: list[str]) -> LauncherStatus: ...

    @abstractmethod
    async def logs(self, service: str, tail: int = 200) -> str: ...
