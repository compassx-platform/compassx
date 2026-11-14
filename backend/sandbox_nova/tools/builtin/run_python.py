"""Tools that execute only inside the sandbox filesystem."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.base import NovaTool


class RunPythonTool(NovaTool):
    name = "python_code"
    description = "Execute Python in this sandbox. Working directory is /workspace."
    parameters = {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    }

    def __init__(self, workspace_root: str, timeout_s: int) -> None:
        self.workspace_root = workspace_root
        self.timeout_s = timeout_s

    def execute(self, arguments: dict[str, Any]) -> str:
        code = str(arguments.get("code") or "")
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return "Python timed out in the sandbox."
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or f"exit {result.returncode}"
