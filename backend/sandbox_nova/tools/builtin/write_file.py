"""Tools that execute only inside the sandbox filesystem."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.base import NovaTool


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
