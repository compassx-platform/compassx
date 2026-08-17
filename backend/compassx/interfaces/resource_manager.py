from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from compassx.models import ExecResult, RuntimeInfo, RuntimeSpec


class ResourceManager(ABC):
    """Provisions infrastructure for runtimes by delegating to drivers.

    Owns the Runtime ID -> infrastructure ID mapping. Callers only ever
    use Runtime IDs.
    """

    @abstractmethod
    async def create_runtime(self, spec: RuntimeSpec, driver_name: str | None = None) -> RuntimeInfo: ...

    @abstractmethod
    async def delete_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def start_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def stop_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def restart_runtime(self, runtime_id: str) -> None: ...

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
