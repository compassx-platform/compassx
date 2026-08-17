"""Agent tools package.

Each tool is a concrete implementation of BaseTool. The tool registry
provides the OpenAI-compatible tool definitions passed to the LLM and
a dispatcher that routes tool_call results to the correct handler.
"""

# BaseTool and ToolResult are imported eagerly — they have no circular deps.
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult

# Registry imports are deferred to break the circular import chain:
#   registry.py  →  fetch_attachment_tool.py  →  base_tool.py
#              →  tools/__init__.py  →  registry.py  (CYCLE)
# Callers that need TOOL_REGISTRY / TOOL_MAP / get_tool_definitions should
# import directly from app.agents.services.agent.tools.registry.


def __getattr__(name: str):
    """Lazy-load registry symbols to avoid circular imports at package init time."""
    if name in ("TOOL_REGISTRY", "TOOL_MAP", "get_tool_definitions"):
        from app.agents.services.agent.tools.registry import (  # noqa: PLC0415
            TOOL_REGISTRY,
            TOOL_MAP,
            get_tool_definitions,
        )
        globals()["TOOL_REGISTRY"] = TOOL_REGISTRY
        globals()["TOOL_MAP"] = TOOL_MAP
        globals()["get_tool_definitions"] = get_tool_definitions
        return globals()[name]
    raise AttributeError(f"module 'app.agents.services.agent.tools' has no attribute {name!r}")


__all__ = [
    "BaseTool",
    "ToolResult",
    "TOOL_REGISTRY",
    "TOOL_MAP",
    "get_tool_definitions",
]
