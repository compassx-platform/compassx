"""Base Asset Change Handler Interface — SOLID compliant Change Capture Architecture.

Defines the abstract interface for capturing, serializing, diffing, accepting, and
reverting changes for any workspace asset type (Notebook, Dashboard, File, Table, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAssetChangeHandler(ABC):
    """
    Abstract Base Class for asset-specific change lifecycle handling (SRP & OCP).

    Each subclass encapsulates the specific knowledge of one asset type:
    - Tool detection & mutation classification
    - Canonical full_name resolution
    - State serialization (for diff comparison)
    - Reversion/rollback execution
    - Acceptance lifecycle hooks
    """

    @property
    @abstractmethod
    def object_type(self) -> str:
        """Canonical object_type identifier (e.g. 'notebook', 'dashboard', 'file', 'table')."""
        ...

    @abstractmethod
    def supports_tool(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Return True if this handler manages changes for the given tool, operation, or payload."""
        ...

    @abstractmethod
    def is_mutating(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Return True if the operation modifies, creates, or deletes state; False if read-only."""
        ...

    @abstractmethod
    def resolve_full_name(
        self,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
        goal: str | None = None,
    ) -> str | None:
        """Determine the canonical full_name (e.g. 'catalog.schema.name' or path) for the asset."""
        ...

    @abstractmethod
    def serialize_current_state(
        self,
        full_name: str,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Serialize the current/new state of the asset into a clean, human-readable,
        diffable text format (JSON, code, SQL, markdown).
        """
        ...

    @abstractmethod
    def revert(self, full_name: str, before_content: str | None) -> bool:
        """
        Roll back the asset's underlying storage/state to before_content.
        If before_content is None or empty, undo initial creation (delete or reset).
        """
        ...

    def accept(self, full_name: str, after_content: str | None) -> bool:
        """
        Lifecycle hook invoked when a user explicitly accepts the change.
        Default implementation is a no-op returning True.
        """
        return True
