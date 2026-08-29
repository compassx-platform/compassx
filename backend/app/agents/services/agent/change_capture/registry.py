"""Change Handler Registry — Open/Closed Principle compliant extension registry.

Allows dynamically registering asset change handlers without modifying core orchestrator
or change capture logic.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.agents.services.agent.change_capture.base import BaseAssetChangeHandler

logger = logging.getLogger(__name__)


class ChangeHandlerRegistry:
    """Registry managing asset change handlers (DIP & OCP)."""

    def __init__(self) -> None:
        self._handlers_by_type: dict[str, BaseAssetChangeHandler] = {}
        self._handlers_list: list[BaseAssetChangeHandler] = []

    def register(self, handler: BaseAssetChangeHandler) -> None:
        """Register an asset change handler."""
        self._handlers_by_type[handler.object_type.lower()] = handler
        # Avoid duplicates in list
        self._handlers_list = [h for h in self._handlers_list if h.object_type.lower() != handler.object_type.lower()]
        self._handlers_list.append(handler)
        logger.debug("Registered change handler for asset type: %s", handler.object_type)

    def get_handler_for_type(self, object_type: str | None) -> Optional[BaseAssetChangeHandler]:
        """Get registered handler for a specific asset object_type."""
        if not object_type:
            return None
        return self._handlers_by_type.get(object_type.lower())

    def find_handler_for_tool(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Optional[BaseAssetChangeHandler]:
        """Find the handler that supports the specified tool, operation, and payload."""
        for handler in self._handlers_list:
            try:
                if handler.supports_tool(tool_name, operation, payload):
                    return handler
            except Exception as exc:
                logger.warning("Error evaluating handler %s for tool %s: %s", handler.object_type, tool_name, exc)
        return None


_global_registry: Optional[ChangeHandlerRegistry] = None


def get_change_handler_registry() -> ChangeHandlerRegistry:
    """Get the global singleton instance of ChangeHandlerRegistry with built-in handlers registered."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ChangeHandlerRegistry()
        from app.agents.services.agent.change_capture.handlers import register_builtin_handlers
        register_builtin_handlers(_global_registry)
    return _global_registry
