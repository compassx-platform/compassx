"""Built-in Asset Change Handlers registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.services.agent.change_capture.registry import ChangeHandlerRegistry


def register_builtin_handlers(registry: ChangeHandlerRegistry) -> None:
    """Register all built-in asset change handlers (OCP)."""
    from app.agents.services.agent.change_capture.handlers.dashboard_handler import DashboardChangeHandler
    from app.agents.services.agent.change_capture.handlers.notebook_handler import NotebookChangeHandler
    from app.agents.services.agent.change_capture.handlers.file_handler import FileChangeHandler
    from app.agents.services.agent.change_capture.handlers.table_handler import TableChangeHandler

    registry.register(DashboardChangeHandler())
    registry.register(NotebookChangeHandler())
    registry.register(FileChangeHandler())
    registry.register(TableChangeHandler())
