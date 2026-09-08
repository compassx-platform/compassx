"""File Change Handler — Encapsulates change capture, serialization, and rollback for plain text and source code files."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Optional

from app.agents.services.agent.change_capture.base import BaseAssetChangeHandler

logger = logging.getLogger(__name__)

READ_ONLY_FILE_TOOLS = {
    "read_file",
    "view_file",
    "list_dir",
    "grep_search",
    "find_by_name",
}

MUTATING_FILE_TOOLS = {
    "write_to_file",
    "replace_file_content",
    "edit_file",
    "create_file",
}


class FileChangeHandler(BaseAssetChangeHandler):
    """Handler managing general filesystem code and text files (SRP)."""

    @property
    def object_type(self) -> str:
        return "file"

    def supports_tool(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        t_lower = tool_name.lower()
        if t_lower in MUTATING_FILE_TOOLS or t_lower in READ_ONLY_FILE_TOOLS or "file" in t_lower:
            return True
        pld = payload or {}
        if "target_file" in pld or "TargetFile" in pld or "file_path" in pld:
            return True
        return False

    def is_mutating(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        t_lower = tool_name.lower()
        if t_lower in READ_ONLY_FILE_TOOLS:
            return False
        if t_lower in MUTATING_FILE_TOOLS or "write" in t_lower or "replace" in t_lower or "edit" in t_lower:
            return True
        return False

    def resolve_full_name(
        self,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
        goal: str | None = None,
    ) -> str | None:
        pld = payload or {}
        ctx = context or {}
        fn = (
            pld.get("TargetFile")
            or pld.get("target_file")
            or pld.get("AbsolutePath")
            or pld.get("path")
            or pld.get("file_path")
            or ctx.get("path")
            or result.get("full_name")
            or result.get("path")
        )
        return str(fn) if fn else "workspace/file"

    def serialize_current_state(
        self,
        full_name: str,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str | None:
        pld = payload or {}
        # Read from payload code content or directly from file
        content = (
            pld.get("CodeContent")
            or pld.get("code_content")
            or pld.get("content")
            or pld.get("code")
            or result.get("content")
            or result.get("code")
        )
        if content and isinstance(content, str):
            return content

        try:
            p = Path(full_name)
            if p.is_file():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass

        return None

    def revert(self, full_name: str, before_content: str | None) -> bool:
        try:
            path_obj = Path(full_name)
            if path_obj.is_absolute() or path_obj.exists():
                if before_content is not None:
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    path_obj.write_text(before_content, encoding="utf-8")
                else:
                    if path_obj.is_file():
                        path_obj.unlink(missing_ok=True)
                return True

            workspace_root = Path(os.environ.get("AGENT_WORKSPACE_ROOT", str(Path(tempfile.gettempdir()) / "agent_workspaces")))
            if workspace_root.exists():
                clean_rel = full_name.lstrip("/\\")
                matched_files = list(workspace_root.glob(f"**/{clean_rel}"))
                for mf in matched_files:
                    if before_content is not None:
                        mf.write_text(before_content, encoding="utf-8")
                    else:
                        if mf.is_file():
                            mf.unlink(missing_ok=True)
                    return True
        except Exception as exc:
            logger.exception("Failed reverting file content for %s: %s", full_name, exc)
            return False
        return False
