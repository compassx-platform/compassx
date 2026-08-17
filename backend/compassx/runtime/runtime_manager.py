"""Default Runtime Manager.

Converts business requests (runtime type + options) into RuntimeSpecs
via the SpecBuilderRegistry and delegates provisioning to the Resource
Manager. Selects the driver per runtime type from the deployment
profile policy. Never imports Docker or Kubernetes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator, Callable

from compassx.interfaces.resource_manager import ResourceManager
from compassx.interfaces.runtime_manager import RuntimeManager
from compassx.models import (
    RuntimeAlreadyExistsError,
    RuntimeInfo,
    RuntimePhase,
)
from compassx.runtime.repository import RuntimeRepository
from compassx.runtime.spec_builders import SpecBuilderRegistry

logger = logging.getLogger(__name__)


def _new_runtime_id() -> str:
    return f"runtime-{uuid.uuid4().hex[:8]}"


class DefaultRuntimeManager(RuntimeManager):
    def __init__(
        self,
        resource_manager: ResourceManager,
        spec_builders: SpecBuilderRegistry,
        repository: RuntimeRepository,
        driver_policy: Callable[[str], str],
        *,
        namespace: str = "",
        env: str = "local",
    ) -> None:
        """driver_policy: runtime_type -> driver name (from deployment profile)."""
        self._resources = resource_manager
        self._builders = spec_builders
        self._repository = repository
        self._driver_policy = driver_policy
        self._namespace = namespace
        self._env = env

    @property
    def resource_manager(self) -> ResourceManager:
        return self._resources

    async def create_runtime(
        self,
        runtime_type: str,
        *,
        runtime_id: str | None = None,
        user_id: str = "",
        workspace_id: str = "",
        options: dict[str, Any] | None = None,
    ) -> RuntimeInfo:
        runtime_id = runtime_id or _new_runtime_id()
        existing = self._repository.find(runtime_id)
        if existing is not None and existing.phase not in (
            RuntimePhase.DELETED,
            RuntimePhase.FAILED,
            RuntimePhase.STOPPED,
            RuntimePhase.MISSING,
        ):
            raise RuntimeAlreadyExistsError(f"Runtime already exists: {runtime_id}")

        builder = self._builders.get(runtime_type)
        spec = builder.build(
            runtime_id,
            user_id=user_id,
            workspace_id=workspace_id,
            namespace=self._namespace,
            env=self._env,
            options=options,
        )
        driver_name = self._driver_policy(runtime_type)
        return await self._resources.create_runtime(spec, driver_name=driver_name)

    async def delete_runtime(self, runtime_id: str) -> None:
        await self._resources.delete_runtime(runtime_id)

    async def start_runtime(self, runtime_id: str) -> None:
        await self._resources.start_runtime(runtime_id)

    async def stop_runtime(self, runtime_id: str) -> None:
        await self._resources.stop_runtime(runtime_id)

    async def suspend_runtime(self, runtime_id: str) -> None:
        # Suspension maps to stop for drivers without pause semantics.
        await self._resources.stop_runtime(runtime_id)
        self._repository.update(runtime_id, phase=RuntimePhase.SUSPENDED)

    async def resume_runtime(self, runtime_id: str) -> None:
        await self._resources.start_runtime(runtime_id)

    async def get_status(self, runtime_id: str) -> RuntimeInfo:
        return await self._resources.get_status(runtime_id)

    async def get_metadata(self, runtime_id: str) -> dict[str, Any]:
        record = self._repository.get(runtime_id)
        return {
            "runtime_id": record.runtime_id,
            "runtime_type": record.runtime_type,
            "driver": record.driver,
            "namespace": record.namespace,
            "user_id": record.user_id,
            "workspace_id": record.workspace_id,
            "phase": record.phase.value,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    async def list_runtimes(
        self, *, user_id: str | None = None, workspace_id: str | None = None
    ) -> list[RuntimeInfo]:
        infos: list[RuntimeInfo] = []
        for record in self._repository.list(
            user_id=user_id, workspace_id=workspace_id
        ):
            infos.append(await self._resources.get_status(record.runtime_id))
        return infos

    async def exec(self, runtime_id: str, command: list[str]):
        return await self._resources.exec(runtime_id, command)

    async def logs(self, runtime_id: str, tail: int | None = None) -> str:
        return await self._resources.logs(runtime_id, tail=tail)

    async def stream_logs(self, runtime_id: str) -> AsyncIterator[str]:
        async for line in self._resources.stream_logs(runtime_id):
            yield line
