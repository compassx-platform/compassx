"""In-memory fakes for platform-layer unit tests."""

from __future__ import annotations

from typing import AsyncIterator

from compassx.interfaces.driver import ResourceDriver
from compassx.interfaces.launcher import Launcher, LauncherStatus, ServiceStatus
from compassx.models import (
    ExecResult,
    RuntimeAlreadyExistsError,
    RuntimeInfo,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeSpec,
)


class FakeDriver(ResourceDriver):
    name = "fake"

    def __init__(self, fail_create: bool = False) -> None:
        self.runtimes: dict[str, RuntimeSpec] = {}
        self.phases: dict[str, RuntimePhase] = {}
        self.calls: list[tuple] = []
        self.fail_create = fail_create

    async def create_runtime(self, spec: RuntimeSpec) -> str:
        self.calls.append(("create", spec.runtime_id))
        if self.fail_create:
            raise RuntimeError("boom")
        if spec.runtime_id in self.runtimes:
            raise RuntimeAlreadyExistsError(spec.runtime_id)
        self.runtimes[spec.runtime_id] = spec
        self.phases[spec.runtime_id] = RuntimePhase.RUNNING
        return f"infra-{spec.runtime_id}"

    def _require(self, runtime_id: str) -> None:
        if runtime_id not in self.runtimes:
            raise RuntimeNotFoundError(runtime_id)

    async def delete_runtime(self, runtime_id: str) -> None:
        self.calls.append(("delete", runtime_id))
        self._require(runtime_id)
        del self.runtimes[runtime_id]
        del self.phases[runtime_id]

    async def start_runtime(self, runtime_id: str) -> None:
        self.calls.append(("start", runtime_id))
        self._require(runtime_id)
        self.phases[runtime_id] = RuntimePhase.RUNNING

    async def stop_runtime(self, runtime_id: str) -> None:
        self.calls.append(("stop", runtime_id))
        self._require(runtime_id)
        self.phases[runtime_id] = RuntimePhase.STOPPED

    async def get_status(self, runtime_id: str) -> RuntimeInfo:
        self._require(runtime_id)
        return RuntimeInfo(
            runtime_id=runtime_id,
            runtime_type=self.runtimes[runtime_id].runtime_type,
            phase=self.phases[runtime_id],
            infra_id=f"infra-{runtime_id}",
        )

    async def list_runtimes(self) -> list[RuntimeInfo]:
        return [await self.get_status(rid) for rid in self.runtimes]

    async def exec(self, runtime_id: str, command: list[str]) -> ExecResult:
        self._require(runtime_id)
        return ExecResult(exit_code=0, stdout=" ".join(command))

    async def logs(self, runtime_id: str, tail: int | None = None) -> str:
        self._require(runtime_id)
        return "line1\nline2"

    async def stream_logs(self, runtime_id: str) -> AsyncIterator[str]:
        self._require(runtime_id)
        for line in ("line1", "line2"):
            yield line

    async def copy_file(
        self, runtime_id: str, src_path: str, dest_path: str, to_runtime: bool = True
    ) -> None:
        self.calls.append(("copy", runtime_id, src_path, dest_path))


class FakeLauncher(Launcher):
    name = "fake"

    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []

    async def start(self, services: list[str]) -> None:
        self.started.extend(services)

    async def stop(self, services: list[str]) -> None:
        self.stopped.extend(services)

    async def restart(self, services: list[str]) -> None:
        await self.stop(services)
        await self.start(services)

    async def status(self, services: list[str]) -> LauncherStatus:
        return LauncherStatus(
            launcher=self.name,
            services=[
                ServiceStatus(name=s, running=s in self.started, healthy=True)
                for s in services
            ],
        )

    async def logs(self, service: str, tail: int = 200) -> str:
        return f"logs for {service}"
