"""Run a command in the sandbox the Build page started.

Callers depend on this port. They do not choose between the sandbox
driver and the legacy dev driver.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Protocol

logger = logging.getLogger(__name__)

CommandTarget = Callable[[str], str]


class SandboxCommandPort(Protocol):
    """Narrow interface: run one shell command, or visit each live runtime."""

    def run(
        self,
        app: Any,
        command: str,
        workspace_folder: str = "",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        ...

    def targets(self, app: Any, timeout: int = 20) -> List[CommandTarget]:
        ...


class BuildSandboxCommands:
    """Prefer the Build sandbox pod, then the legacy dev driver."""

    def run(
        self,
        app: Any,
        command: str,
        workspace_folder: str = "",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        sandbox_result = self._run_in_sandbox(app, command, timeout=timeout)
        if sandbox_result is not None:
            return sandbox_result
        return self._run_in_dev_driver(app, command, workspace_folder=workspace_folder, timeout=timeout)

    def targets(self, app: Any, timeout: int = 20) -> List[CommandTarget]:
        """Every live runtime for this app. Used when a login must be read from each pod."""
        found: List[CommandTarget] = []
        app_id = getattr(app, "id", "")
        try:
            from app.sandbox.service import sandbox_service

            inst = sandbox_service.find_active_sandbox(
                sandbox_id=f"dev-app-{app_id}",
                consumer_key=f"app_{app_id}",
                consumer_module="app",
            )
            if inst is not None:
                driver = sandbox_service._get_driver_for_mode(inst.runtime_mode)

                def _sandbox_exec(command: str, _driver=driver, _inst=inst, _timeout=timeout) -> str:
                    result = _driver.exec_command(_inst, command, timeout=_timeout)
                    return f"{getattr(result, 'stdout', '') or ''}\n{getattr(result, 'stderr', '') or ''}"

                found.append(_sandbox_exec)
        except Exception:
            logger.debug("No sandbox runtime for %s", app_id, exc_info=True)

        try:
            from app.services.drivers.factory import driver_factory

            dev = driver_factory.get_dev_driver()

            def _dev_exec(command: str, _dev=dev, _timeout=timeout) -> str:
                result = _dev.exec_command_in_dev(app, command, timeout=_timeout)
                return (result or {}).get("output") or ""

            found.append(_dev_exec)
        except Exception:
            logger.debug("No dev driver runtime for %s", app_id, exc_info=True)
        return found

    def _run_in_sandbox(self, app: Any, command: str, timeout: int) -> Dict[str, Any] | None:
        app_id = getattr(app, "id", "")
        try:
            from app.sandbox.service import sandbox_service

            inst = sandbox_service.find_active_sandbox(
                sandbox_id=f"dev-app-{app_id}",
                consumer_key=f"app_{app_id}",
                consumer_module="app",
            )
            if inst is None:
                return None
            driver = sandbox_service._get_driver_for_mode(inst.runtime_mode)
            result = driver.exec_command(inst, command, timeout=timeout)
            output = f"{getattr(result, 'stdout', '') or ''}\n{getattr(result, 'stderr', '') or ''}"
            return {
                "success": bool(getattr(result, "success", False)),
                "exit_code": getattr(result, "exit_code", 1),
                "output": output,
            }
        except Exception:
            logger.debug("Sandbox command failed for %s", app_id, exc_info=True)
            return None

    def _run_in_dev_driver(
        self,
        app: Any,
        command: str,
        workspace_folder: str,
        timeout: int,
    ) -> Dict[str, Any]:
        try:
            from app.services.drivers.factory import driver_factory

            dev = driver_factory.get_dev_driver()
            result = dev.exec_command_in_dev(
                app,
                command,
                workspace_folder=workspace_folder,
                timeout=timeout,
            )
            return result or {"success": False, "exit_code": 1, "output": ""}
        except Exception as exc:
            logger.debug("Dev driver command failed for %s", getattr(app, "id", ""), exc_info=True)
            return {"success": False, "exit_code": 1, "output": str(exc)}


build_sandbox_commands = BuildSandboxCommands()
