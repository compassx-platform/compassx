"""Centralized Sandbox Orchestration Service.

Public methods stay on SandboxService. Each one forwards to one application type.
"""
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.sandbox.drivers.factory import sandbox_driver_factory
from app.sandbox.interfaces import BaseSandboxDriver, SandboxHandle
from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec
from app.sandbox.shared.support import _normalize_key, logger

__all__ = ["SandboxService", "sandbox_service", "_normalize_key", "logger"]


class SandboxService:
    """Centralized management service for isolated compute sandboxes across platform profiles."""

    def __init__(self):
        self._instances: Dict[str, SandboxInstance] = {}

    def _get_driver_for_mode(self, mode: Optional[str] = None) -> BaseSandboxDriver:
        return sandbox_driver_factory.get_driver(mode)

    def find_active_sandbox(
        self,
        sandbox_id: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_module: Optional[str] = None,
    ) -> Optional[SandboxInstance]:
        from app.sandbox.lifecycle.application.find_active_sandbox import find_active_sandbox
        return find_active_sandbox(self, sandbox_id, consumer_key, consumer_module)

    def ensure_sandbox(self, spec: SandboxSpec) -> SandboxInstance:
        from app.sandbox.lifecycle.application.ensure_sandbox import ensure_sandbox
        return ensure_sandbox(self, spec)

    def provision_sandbox(self, spec: SandboxSpec) -> SandboxHandle:
        from app.sandbox.lifecycle.application.provision_sandbox import provision_sandbox
        return provision_sandbox(self, spec)

    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInstance]:
        from app.sandbox.lifecycle.application.get_sandbox import get_sandbox
        return get_sandbox(self, sandbox_id)

    def get_handle(self, sandbox_id: str) -> Optional[SandboxHandle]:
        from app.sandbox.lifecycle.application.get_handle import get_handle
        return get_handle(self, sandbox_id)

    def list_sandboxes(
        self,
        workspace_id: Optional[str] = None,
        consumer_module: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SandboxInstance]:
        from app.sandbox.lifecycle.application.list_sandboxes import list_sandboxes
        return list_sandboxes(self, workspace_id, consumer_module, status)

    def terminate_sandbox(self, sandbox_id: str) -> bool:
        from app.sandbox.lifecycle.application.terminate_sandbox import terminate_sandbox
        return terminate_sandbox(self, sandbox_id)

    def suspend_sandbox(self, sandbox_id: str) -> bool:
        from app.sandbox.lifecycle.application.suspend_sandbox import suspend_sandbox
        return suspend_sandbox(self, sandbox_id)

    def resume_sandbox(self, sandbox_id: str) -> bool:
        from app.sandbox.lifecycle.application.resume_sandbox import resume_sandbox
        return resume_sandbox(self, sandbox_id)

    def exec_in_sandbox(
        self,
        sandbox_id: str,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        from app.sandbox.lifecycle.application.exec_in_sandbox import exec_in_sandbox
        return exec_in_sandbox(self, sandbox_id, command, working_dir, env, timeout)

    def get_sandbox_logs(self, sandbox_id: str, max_lines: int = 200) -> str:
        from app.sandbox.lifecycle.application.get_sandbox_logs import get_sandbox_logs
        return get_sandbox_logs(self, sandbox_id, max_lines)

    async def stream_sandbox_logs(self, sandbox_id: str, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        from app.sandbox.lifecycle.application.stream_sandbox_logs import stream_sandbox_logs
        async for line in stream_sandbox_logs(self, sandbox_id, tail_lines):
            yield line

    async def handle_terminal_websocket(
        self,
        websocket: Any,
        sandbox_id: str,
        cols: int = 100,
        rows: int = 30,
        working_dir: Optional[str] = None,
        command: Optional[str] = None,
        agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        from app.sandbox.lifecycle.application.handle_terminal_websocket import handle_terminal_websocket
        await handle_terminal_websocket(
            self, websocket, sandbox_id, cols, rows, working_dir, command, agent, session_id
        )


sandbox_service = SandboxService()
