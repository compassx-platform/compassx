"""Change Capture Service — Backwards compatibility facade for app.agents.services.agent.change_capture."""

from app.agents.services.agent.change_capture import (
    BaseAssetChangeHandler,
    ChangeHandlerRegistry,
    accept_change,
    bulk_review_changes,
    capture_change,
    capture_tool_change,
    get_change_handler_registry,
    get_change_record,
    get_changes_for_session,
    reject_change,
)
from app.agents.services.agent.change_capture.service import (
    _compute_diff_counts,
    _normalize_text,
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
    "_normalize_text",
    "_compute_diff_counts",
]
