"""Abstract base class for Git provider implementations.

All provider-specific operations (PRs, comments, work items, diffs) must be
implemented by a concrete subclass. The rest of the codebase depends only on
this interface — adding a new provider never requires touching pipeline code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GitProvider(ABC):
    """Interface for a Git hosting provider."""

    # ── Pull request operations ───────────────────────────────────────────────

    @abstractmethod
    def create_pr(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        """Create a pull request. Returns ``{"url": ..., "number": ...}``."""

    @abstractmethod
    def post_pr_comment(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        """Post a comment on a pull request."""

    @abstractmethod
    def set_pr_ready(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        """Remove draft status from a pull request."""

    # ── Work item / issue operations ──────────────────────────────────────────

    @abstractmethod
    def post_workitem_comment(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        """Post a comment on a work item or issue."""

    @abstractmethod
    def update_workitem_status(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        """Update the state/status of a work item or issue."""

    # ── Diff fetching ─────────────────────────────────────────────────────────

    @abstractmethod
    def fetch_pr_diff(self, args: dict[str, Any], token: str) -> dict[str, Any]:
        """Fetch changed files and unified diffs for a pull request.

        Returns ``{"diffs": [{"filename": str, "patch": str}, ...]}``.
        """
