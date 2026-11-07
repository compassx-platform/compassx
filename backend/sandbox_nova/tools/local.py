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


class ListFilesTool(NovaTool):
    name = "list_files"
    description = "List files under a path in /workspace."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
    }

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    def execute(self, arguments: dict[str, Any]) -> str:
        target = resolve_workspace_path(self.workspace_root, str(arguments.get("path") or "."))
        if not os.path.isdir(target):
            return f"Not a directory: {target}"
        names = sorted(os.listdir(target))[:400]
        return "\n".join(names) or "(empty)"


class ReadFileTool(NovaTool):
    name = "read_file"
    description = "Read a UTF-8 file from /workspace."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    def execute(self, arguments: dict[str, Any]) -> str:
        target = resolve_workspace_path(self.workspace_root, str(arguments.get("path") or ""))
        with open(target, encoding="utf-8", errors="replace") as handle:
            return handle.read(120_000)


class WriteFileTool(NovaTool):
    name = "write_file"
    description = "Write a UTF-8 file under /workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    def execute(self, arguments: dict[str, Any]) -> str:
        target = resolve_workspace_path(self.workspace_root, str(arguments.get("path") or ""))
        os.makedirs(os.path.dirname(target) or self.workspace_root, exist_ok=True)
        content = str(arguments.get("content") or "")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)
        return f"Wrote {len(content.encode('utf-8'))} bytes to {target}"
