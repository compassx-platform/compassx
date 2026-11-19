"""Write a single markdown plan. Plan mode is the only caller."""

from __future__ import annotations

import os
import re
from typing import Any

from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.base import NovaTool

_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class WritePlanTool(NovaTool):
    name = "write_plan"
    description = "Write one markdown plan at /workspace/.plans/<name>.md. Does not start the work."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["name", "content"],
    }

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root

    def execute(self, arguments: dict[str, Any]) -> str:
        raw = str(arguments.get("name") or arguments.get("path") or "").strip().replace("\\", "/")
        name = raw.split("/")[-1]
        if name.endswith(".md"):
            name = name[:-3]
        if not _NAME.fullmatch(name):
            return "Plan name must be kebab-case."
        content = str(arguments.get("content") or "")
        if not content.strip():
            return "A plan needs markdown content."
        relative = f".plans/{name}.md"
        target = resolve_workspace_path(self.workspace_root, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)
        return f"Wrote the plan {relative}"
