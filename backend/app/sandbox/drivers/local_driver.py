"""Local process and directory driver for the Sandbox Module."""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
import uuid

from app.sandbox.interfaces import BaseSandboxDriver
from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec, SandboxStatus

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = os.path.join(os.path.expanduser("~"), ".compassx", "sandboxes")


class LocalSandboxDriver(BaseSandboxDriver):
    """Manages isolated compute sandboxes as local workspace directories and child processes."""

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_sandbox_dir(self, sandbox_id: str) -> str:
        sb_dir = os.path.join(self.base_dir, sandbox_id)
        os.makedirs(sb_dir, exist_ok=True)
        return sb_dir

    def _get_metadata_path(self, sandbox_id: str) -> str:
        return os.path.join(self._get_sandbox_dir(sandbox_id), "sandbox_meta.json")

    def _get_log_path(self, sandbox_id: str) -> str:
        return os.path.join(self._get_sandbox_dir(sandbox_id), "sandbox.log")

    def provision(self, spec: SandboxSpec) -> SandboxInstance:
        """Set up local isolated sandbox directory and write metadata."""
        sandbox_id = spec.sandbox_id or f"sb-{uuid.uuid4().hex[:10]}"
        sb_dir = self._get_sandbox_dir(sandbox_id)
        workspace_dir = os.path.join(sb_dir, "workspace")
        os.makedirs(workspace_dir, exist_ok=True)

        endpoints = {}
        for port in spec.ports:
            endpoints[str(port)] = f"http://localhost:{port}"

        instance = SandboxInstance(
            id=sandbox_id,
            name=spec.name,
            consumer_module=spec.consumer_module,
            workspace_id=spec.workspace_id,
            status=SandboxStatus.RUNNING,
            runtime_mode="local",
            image="host-python",
            endpoints=endpoints,
            ports=spec.ports,
            working_dir=workspace_dir,
            created_at=datetime.now(timezone.utc).isoformat(),
            started_at=datetime.now(timezone.utc).isoformat(),
            labels=spec.labels,
            metadata={
                **spec.metadata,
                "sandbox_dir": sb_dir,
                "env_vars": spec.env_vars,
            },
        )

        with open(self._get_metadata_path(sandbox_id), "w", encoding="utf-8") as f:
            json.dump(instance.dict(), f, indent=2)

        # Write initial entry to log
        with open(self._get_log_path(sandbox_id), "a", encoding="utf-8") as f:
            f.write(f"[{instance.created_at}] Sandbox '{spec.name}' ({sandbox_id}) provisioned.\n")

        return instance

    def terminate(self, instance: SandboxInstance) -> bool:
        """Clean up local sandbox directory."""
        try:
            sb_dir = os.path.join(self.base_dir, instance.id)
            if os.path.exists(sb_dir):
                # We can archive or remove
                shutil.rmtree(sb_dir, ignore_errors=True)
            instance.status = SandboxStatus.TERMINATED
            instance.stopped_at = datetime.now(timezone.utc).isoformat()
            return True
        except Exception as exc:
            logger.warning("Error terminating local sandbox %s: %s", instance.id, exc)
            return False

    def suspend(self, instance: SandboxInstance) -> bool:
        """Mark local sandbox as suspended."""
        instance.status = SandboxStatus.SUSPENDED
        meta_path = self._get_metadata_path(instance.id)
        if os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(instance.dict(), f, indent=2)
        return True

    def resume(self, instance: SandboxInstance) -> bool:
        """Mark local sandbox as active/running."""
        instance.status = SandboxStatus.RUNNING
        meta_path = self._get_metadata_path(instance.id)
        if os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(instance.dict(), f, indent=2)
        return True

    def get_status(self, instance: SandboxInstance) -> SandboxStatus:
        """Check status of local sandbox."""
        sb_dir = os.path.join(self.base_dir, instance.id)
        if not os.path.exists(sb_dir):
            return SandboxStatus.TERMINATED
        return instance.status

    def exec_command(
        self,
        instance: SandboxInstance,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute a command locally in the sandbox working directory."""
        start_time = time.time()
        effective_dir = working_dir or instance.working_dir
        if not os.path.exists(effective_dir):
            effective_dir = self._get_sandbox_dir(instance.id)

        custom_env = os.environ.copy()
        if instance.metadata.get("env_vars"):
            custom_env.update(instance.metadata["env_vars"])
        if env:
            custom_env.update(env)

        is_shell = isinstance(command, str)
        try:
            res = subprocess.run(
                command,
                cwd=effective_dir,
                env=custom_env,
                shell=is_shell,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = round(time.time() - start_time, 3)

            # Append to sandbox log
            log_path = self._get_log_path(instance.id)
            with open(log_path, "a", encoding="utf-8") as f:
                cmd_str = command if isinstance(command, str) else " ".join(command)
                f.write(f"\n$ {cmd_str}\n{res.stdout}{res.stderr}\n")

            return ExecResult(
                exit_code=res.returncode,
                stdout=res.stdout or "",
                stderr=res.stderr or "",
                duration_seconds=duration,
                success=(res.returncode == 0),
            )
        except subprocess.TimeoutExpired:
            duration = round(time.time() - start_time, 3)
            return ExecResult(
                exit_code=124,
                stderr=f"Command timed out after {timeout} seconds",
                duration_seconds=duration,
                success=False,
            )
        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            return ExecResult(
                exit_code=1,
                stderr=f"Execution error: {exc}",
                duration_seconds=duration,
                success=False,
            )

    def get_logs(self, instance: SandboxInstance, max_lines: int = 200) -> str:
        """Fetch logs from local sandbox log file."""
        log_path = self._get_log_path(instance.id)
        if not os.path.exists(log_path):
            return f"[No logs found for sandbox {instance.id}]"
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return "".join(lines[-max_lines:])
        except Exception as exc:
            return f"[Error reading logs: {exc}]"

    async def stream_logs(self, instance: SandboxInstance, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        """Stream logs from local log file."""
        log_path = self._get_log_path(instance.id)
        if not os.path.exists(log_path):
            yield f"[Waiting for logs for sandbox {instance.id}...]\n"
            return
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                for l in lines[-tail_lines:]:
                    yield l
            # Follow file
            last_pos = os.path.getsize(log_path)
            for _ in range(60):
                await asyncio.sleep(1)
                curr_size = os.path.getsize(log_path)
                if curr_size > last_pos:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_content = f.read()
                        last_pos = curr_size
                        yield new_content
        except Exception as exc:
            yield f"[Stream error: {exc}]\n"

    def get_endpoints(self, instance: SandboxInstance) -> Dict[str, str]:
        return instance.endpoints

    def discover_active_instances(self) -> List[SandboxInstance]:
        """Discover active local sandboxes from disk."""
        instances = []
        if not os.path.exists(self.base_dir):
            return instances
        for name in os.listdir(self.base_dir):
            sb_dir = os.path.join(self.base_dir, name)
            meta_file = os.path.join(sb_dir, "sandbox_meta.json")
            if os.path.isdir(sb_dir) and os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        instances.append(SandboxInstance(**data))
                except Exception:
                    pass
        return instances
