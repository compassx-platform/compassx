from typing import Any, Dict, List, Optional

from app.sandbox.models import ExecResult


class ExecInSandbox:
    def execute(
        self,
        service,
        sandbox_id: str,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            return ExecResult(
                exit_code=1,
                stderr=f"Sandbox '{sandbox_id}' not found",
                success=False,
            )
        driver = service._get_driver_for_mode(instance.runtime_mode)
        return driver.exec_command(
            instance,
            command=command,
            working_dir=working_dir or instance.working_dir,
            env=env,
            timeout=timeout,
        )


def exec_in_sandbox(service, sandbox_id, command, working_dir=None, env=None, timeout=60):
    return ExecInSandbox().execute(service, sandbox_id, command, working_dir, env, timeout)
