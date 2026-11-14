"""Tools that execute only inside the sandbox filesystem."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.base import NovaTool


class RunShellTool(NovaTool):
    name = "run_shell"
    description = "Run a shell command inside /workspace."
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }

    def __init__(self, workspace_root: str, timeout_s: int) -> None:
        self.workspace_root = workspace_root
        self.timeout_s = timeout_s

    def execute(self, arguments: dict[str, Any]) -> str:
        command = str(arguments.get("command") or "")
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return "Command timed out in the sandbox."
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or f"exit {result.returncode}"
