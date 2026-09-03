"""Default Resource Manager — delegates infra work to drivers.

Owns the Runtime ID -> infra ID mapping via the RuntimeRepository.
Structured logging on every operation.
"""

from __future__ import annotations

import logging
import time
from typing import AsyncIterator, Callable

from compassx.interfaces.driver import ResourceDriver
from compassx.interfaces.resource_manager import ResourceManager
from compassx.models import (
    DriverUnavailableError,
    ExecResult,
    RuntimeInfo,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeSpec,
)
from compassx.runtime.repository import RuntimeRecord, RuntimeRepository

logger = logging.getLogger(__name__)


class DriverRegistry:
    """Lazily instantiates and caches drivers by name."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], ResourceDriver]] = {}
        self._instances: dict[str, ResourceDriver] = {}

    def register(self, name: str, factory: Callable[[], ResourceDriver]) -> None:
        self._factories[name] = factory

    def get(self, name: str) -> ResourceDriver:
        if name in self._instances:
            return self._instances[name]
        factory = self._factories.get(name)
        if factory is None:
            known = ", ".join(sorted(self._factories)) or "<none>"
            raise DriverUnavailableError(
                f"Unknown driver: {name}. Registered: {known}"
            )
        instance = factory()
        self._instances[name] = instance
        return instance

    def list_drivers(self) -> list[str]:
        return sorted(self._factories)


class DefaultResourceManager(ResourceManager):
    def __init__(
        self,
        drivers: DriverRegistry,
        repository: RuntimeRepository,
        default_driver: str = "local",
    ) -> None:
        self._drivers = drivers
        self._repository = repository
        self._default_driver = default_driver

    @property
    def default_driver(self) -> str:
        return self._default_driver

    # ── helpers ──────────────────────────────────────────────────────────

    def _driver_for(self, runtime_id: str) -> ResourceDriver:
        record = self._repository.get(runtime_id)
        return self._drivers.get(record.driver)

    # ── lifecycle ────────────────────────────────────────────────────────

    async def create_runtime(
        self, spec: RuntimeSpec, driver_name: str | None = None
    ) -> RuntimeInfo:
        driver_name = driver_name or self._default_driver
        driver = self._drivers.get(driver_name)
        started = time.monotonic()

        record = RuntimeRecord(
            runtime_id=spec.runtime_id,
            runtime_type=spec.runtime_type,
            driver=driver_name,
            namespace=spec.namespace,
            user_id=spec.user_id,
            workspace_id=spec.workspace_id,
            phase=RuntimePhase.CREATING,
        )
        self._repository.save(record)

        try:
            infra_id = await driver.create_runtime(spec)
        except Exception:
            self._repository.update(spec.runtime_id, phase=RuntimePhase.FAILED)
            logger.exception(
                "runtime.create failed runtime_id=%s driver=%s type=%s user=%s workspace=%s",
                spec.runtime_id,
                driver_name,
                spec.runtime_type,
                spec.user_id,
                spec.workspace_id,
            )
            raise

        self._repository.update(
            spec.runtime_id, infra_id=infra_id, phase=RuntimePhase.PENDING
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "runtime.create runtime_id=%s driver=%s type=%s duration_ms=%s user=%s workspace=%s",
            spec.runtime_id,
            driver_name,
            spec.runtime_type,
            duration_ms,
            spec.user_id,
            spec.workspace_id,
        )
        return RuntimeInfo(
            runtime_id=spec.runtime_id,
            runtime_type=spec.runtime_type,
            phase=RuntimePhase.PENDING,
            infra_id=infra_id,
        )

    async def delete_runtime(self, runtime_id: str) -> None:
        driver = self._driver_for(runtime_id)
        try:
            await driver.delete_runtime(runtime_id)
        except RuntimeNotFoundError:
            pass  # infra already gone; still clear the record
        self._repository.delete(runtime_id)
        logger.info("runtime.delete runtime_id=%s", runtime_id)

    async def start_runtime(self, runtime_id: str) -> None:
        try:
            await self._driver_for(runtime_id).start_runtime(runtime_id)
            self._repository.update(runtime_id, phase=RuntimePhase.PENDING)
            logger.info("runtime.start runtime_id=%s", runtime_id)
        except RuntimeNotFoundError:
            self._repository.update(runtime_id, phase=RuntimePhase.MISSING, infra_id="")
            raise

    async def stop_runtime(self, runtime_id: str) -> None:
        await self._driver_for(runtime_id).stop_runtime(runtime_id)
        self._repository.update(runtime_id, phase=RuntimePhase.STOPPED)
        logger.info("runtime.stop runtime_id=%s", runtime_id)

    async def restart_runtime(self, runtime_id: str) -> None:
        driver = self._driver_for(runtime_id)
        await driver.stop_runtime(runtime_id)
        await driver.start_runtime(runtime_id)
        self._repository.update(runtime_id, phase=RuntimePhase.PENDING)
        logger.info("runtime.restart runtime_id=%s", runtime_id)

    # ── inspection ───────────────────────────────────────────────────────

    async def get_status(self, runtime_id: str) -> RuntimeInfo:
        record = self._repository.get(runtime_id)
        driver = self._drivers.get(record.driver)
        try:
            info = await driver.get_status(runtime_id)
        except RuntimeNotFoundError:
            if record.phase != RuntimePhase.MISSING:
                self._repository.update(runtime_id, phase=RuntimePhase.MISSING, infra_id="")
            return RuntimeInfo(
                runtime_id=runtime_id,
                runtime_type=record.runtime_type,
                phase=RuntimePhase.MISSING,
            )
        if info.phase != record.phase:
            self._repository.update(runtime_id, phase=info.phase)
        info.runtime_type = info.runtime_type or record.runtime_type
        return info

    async def list_runtimes(self) -> list[RuntimeInfo]:
        infos: list[RuntimeInfo] = []
        for record in self._repository.list():
            try:
                infos.append(await self.get_status(record.runtime_id))
            except RuntimeNotFoundError:
                continue
        return infos

    # ── interaction ──────────────────────────────────────────────────────

    async def exec(self, runtime_id: str, command: list[str]) -> ExecResult:
        return await self._driver_for(runtime_id).exec(runtime_id, command)

    async def logs(self, runtime_id: str, tail: int | None = None) -> str:
        return await self._driver_for(runtime_id).logs(runtime_id, tail=tail)

    async def stream_logs(self, runtime_id: str) -> AsyncIterator[str]:
        driver = self._driver_for(runtime_id)
        async for line in driver.stream_logs(runtime_id):
            yield line

    async def copy_file(
        self, runtime_id: str, src_path: str, dest_path: str, to_runtime: bool = True
    ) -> None:
        await self._driver_for(runtime_id).copy_file(
            runtime_id, src_path, dest_path, to_runtime=to_runtime
        )
