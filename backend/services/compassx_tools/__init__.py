"""CompassX Tools SDK (compassx-tools)

Provides the `@cx.tool` decorator and `cx.connections.get()` client resolver
for authoring user-defined agent tools.
"""

from __future__ import annotations

import sys
from typing import Any, Callable

from .decorator import tool, extract_param_schema
from .connections import connections, ConnectionRegistry, ConnectionClient, ConnectionUnreachableError
from .promotion import promote, PromotionResult


class ToolsNamespace:
    """Namespace for tool authoring and catalog operations."""
    promote = staticmethod(promote)


tools = ToolsNamespace()

__all__ = [
    "tool",
    "promote",
    "tools",
    "connections",
    "ConnectionRegistry",
    "ConnectionClient",
    "ConnectionUnreachableError",
    "extract_param_schema",
    "PromotionResult",
]

# Provide self-referential `cx` module alias for convenience
cx = sys.modules[__name__]
