from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from compassx.models import ExecResult, RuntimeInfo, RuntimeSpec


class ResourceDriver(ABC):
    """Infrastructure-specific runtime operations (strategy pattern).

    Implementations: LocalDriver (processes), DockerDriver (containers),
    KubernetesDriver (pods/deployments). All infra exceptions must be
    translated into ``compassx.models.exceptions`` types.
    """

    name: str = "abstract"

    @abstractmethod
    async def create_runtime(self, spec: RuntimeSpec) -> str:
        """Provision infrastructure for the spec. Returns the infra ID
        (container id, deployment name, PID) — internal use only."""

    @abstractmethod
    async def delete_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def start_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def stop_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def get_status(self, runtime_id: str) -> RuntimeInfo: ...

    @abstractmethod
    async def list_runtimes(self) -> list[RuntimeInfo]: ...

    @abstractmethod
    async def exec(self, runtime_id: str, command: list[str]) -> ExecResult: ...

    @abstractmethod
    async def logs(self, runtime_id: str, tail: int | None = None) -> str: ...

    @abstractmethod
    def stream_logs(self, runtime_id: str) -> AsyncIterator[str]: ...

    @abstractmethod
    async def copy_file(
        self, runtime_id: str, src_path: str, dest_path: str, to_runtime: bool = True
    ) -> None: ...
