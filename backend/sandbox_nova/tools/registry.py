"""Composable tool registry for Nova."""

from __future__ import annotations

from typing import Any, Iterable

from sandbox_nova.config import NovaSettings
from sandbox_nova.tools.base import NovaTool
from sandbox_nova.tools.local import ListFilesTool, ReadFileTool, RunPythonTool, RunShellTool, WriteFileTool
from sandbox_nova.tools.platform import PLATFORM_TOOL_SPECS, PlatformTool


class ToolRegistry:
    def __init__(self, tools: Iterable[NovaTool] | None = None) -> None:
        self._tools: dict[str, NovaTool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: NovaTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> NovaTool | None:
        return self._tools.get(name)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [tool.openai_definition() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            return tool.execute(arguments or {})
        except Exception as exc:
            return f"Tool {name} failed: {exc}"


def build_default_registry(settings: NovaSettings) -> ToolRegistry:
    registry = ToolRegistry([
        RunPythonTool(settings.workspace_root, settings.tool_timeout_s),
        RunShellTool(settings.workspace_root, settings.tool_timeout_s),
        ListFilesTool(settings.workspace_root),
        ReadFileTool(settings.workspace_root),
        WriteFileTool(settings.workspace_root),
    ])
    for name, description, parameters in PLATFORM_TOOL_SPECS:
        registry.register(PlatformTool(name, description, parameters, settings))
    return registry
