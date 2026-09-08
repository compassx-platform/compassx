"""Change Capture package — Modular, SOLID-compliant change tracking and rollback architecture."""

from app.agents.services.agent.change_capture.base import BaseAssetChangeHandler
from app.agents.services.agent.change_capture.registry import (
    ChangeHandlerRegistry,
    get_change_handler_registry,
)
from app.agents.services.agent.change_capture.service import (
    accept_change,
    bulk_review_changes,
    capture_change,
    capture_tool_change,
    get_change_record,
    get_changes_for_session,
    reject_change,
)

__all__ = [
    "BaseAssetChangeHandler",
    "ChangeHandlerRegistry",
    "get_change_handler_registry",
    "capture_change",
    "capture_tool_change",
    "accept_change",
    "reject_change",
    "bulk_review_changes",
    "get_change_record",
    "get_changes_for_session",
]
