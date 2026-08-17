from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from compassx.models import RuntimeInfo


class RuntimeManager(ABC):
    """Manages user execution environments (notebooks, jobs, agents...).

    Converts business requests into RuntimeSpecs via registered builders
    and delegates provisioning to the Resource Manager. Never talks to
    Docker or Kubernetes directly.
    """

    @abstractmethod
    async def create_runtime(
        self,
        runtime_type: str,
        *,
        runtime_id: str | None = None,
        user_id: str = "",
        workspace_id: str = "",
        options: dict[str, Any] | None = None,
    ) -> RuntimeInfo: ...

    @abstractmethod
    async def delete_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def start_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def stop_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def suspend_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def resume_runtime(self, runtime_id: str) -> None: ...

    @abstractmethod
    async def get_status(self, runtime_id: str) -> RuntimeInfo: ...

    @abstractmethod
    async def get_metadata(self, runtime_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def list_runtimes(
        self, *, user_id: str | None = None, workspace_id: str | None = None
    ) -> list[RuntimeInfo]: ...

    @abstractmethod
    async def exec(self, runtime_id: str, command: list[str]): ...

    async def logs(self, runtime_id: str, tail: int | None = None) -> str: ...

    @abstractmethod
    def stream_logs(self, runtime_id: str) -> AsyncIterator[str]: ...
