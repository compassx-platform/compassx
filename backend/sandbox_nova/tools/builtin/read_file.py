"""Tools that execute only inside the sandbox filesystem."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.base import NovaTool


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
