"""Tools that execute only inside the sandbox filesystem."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.base import NovaTool


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
