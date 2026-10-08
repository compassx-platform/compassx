"""Abstract base driver interface and handle definition for the Sandbox module."""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
import logging

from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec, SandboxStatus

logger = logging.getLogger(__name__)


class BaseSandboxDriver(ABC):
    """Abstract interface that all infrastructure drivers (Docker, Kubernetes, Local) must implement."""

    @abstractmethod
    def provision(self, spec: SandboxSpec) -> SandboxInstance:
        """Provision the sandbox compute resources and start the runtime container/pod."""
        pass

    @abstractmethod
    def terminate(self, instance: SandboxInstance) -> bool:
        """Completely destroy and clean up the sandbox compute resources."""
        pass

    @abstractmethod
    def suspend(self, instance: SandboxInstance) -> bool:
        """Scale down or pause the sandbox compute while preserving data volumes."""
        pass

    @abstractmethod
    def resume(self, instance: SandboxInstance) -> bool:
        """Scale up or unpause the suspended sandbox compute."""
        pass

    @abstractmethod
    def get_status(self, instance: SandboxInstance) -> SandboxStatus:
        """Query live runtime status of the sandbox container/pod."""
        pass

    @abstractmethod
    def exec_command(
        self,
        instance: SandboxInstance,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute a synchronous command inside the sandbox."""
        pass

    @abstractmethod
    def get_logs(self, instance: SandboxInstance, max_lines: int = 200) -> str:
        """Fetch historical stdout/stderr logs from the sandbox."""
        pass

    @abstractmethod
    async def stream_logs(self, instance: SandboxInstance, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        """Stream live logs from the sandbox."""
        pass

    @abstractmethod
    def get_endpoints(self, instance: SandboxInstance) -> Dict[str, str]:
        """Resolve browser/service reachable URLs for the exposed ports."""
        pass

    def discover_active_instances(self) -> List[SandboxInstance]:
        """Discover running sandboxes managed by this driver from the underlying infrastructure."""
        return []


class SandboxHandle:
    """Convenience handle wrapping a live SandboxInstance and its driver for consumer modules."""

    def __init__(self, instance: SandboxInstance, driver: BaseSandboxDriver, service=None):
        self._instance = instance
        self._driver = driver
        self._service = service

    @property
    def id(self) -> str:
        return self._instance.id

    @property
    def name(self) -> str:
        return self._instance.name

    @property
    def status(self) -> SandboxStatus:
        return self._instance.status

    @property
    def endpoints(self) -> Dict[str, str]:
        return self._instance.endpoints

    @property
    def instance(self) -> SandboxInstance:
        return self._instance

    def exec(
        self,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute a command synchronously inside this sandbox."""
        return self._driver.exec_command(
            self._instance,
            command=command,
            working_dir=working_dir or self._instance.working_dir,
            env=env,
            timeout=timeout,
        )

    def get_logs(self, max_lines: int = 200) -> str:
        """Retrieve stdout/stderr logs."""
        return self._driver.get_logs(self._instance, max_lines=max_lines)

    async def stream_logs(self, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        """Stream logs asynchronously."""
        async for line in self._driver.stream_logs(self._instance, tail_lines=tail_lines):
            yield line

    def suspend(self) -> bool:
        """Suspend compute resources."""
        ok = self._driver.suspend(self._instance)
        if ok:
            self._instance.status = SandboxStatus.SUSPENDED
        return ok

    def resume(self) -> bool:
        """Resume compute resources."""
        ok = self._driver.resume(self._instance)
        if ok:
            self._instance.status = SandboxStatus.RUNNING
        return ok

    def terminate(self) -> bool:
        """Terminate and clean up sandbox."""
        ok = self._driver.terminate(self._instance)
        if ok:
            self._instance.status = SandboxStatus.TERMINATED
        return ok

    def refresh_status(self) -> SandboxStatus:
        """Refresh runtime status against infrastructure."""
        new_status = self._driver.get_status(self._instance)
        self._instance.status = new_status
        return new_status
