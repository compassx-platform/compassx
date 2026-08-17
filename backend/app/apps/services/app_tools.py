"""App-scoped tools available to the LLM in the App IDE chat.

These tools let the LLM read, write, list, rename, and delete files
in the app's branch, and run shell commands in the terminal.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Tool definitions for the LLM API (OpenAI function calling format)
APP_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file in the app workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path, e.g. 'src/App.tsx'",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file in the app workspace with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the app workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to list, default is root ''",
                        "default": "",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file from the app workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path to delete",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Rename or move a file within the app workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "Current file path",
                    },
                    "new_path": {
                        "type": "string",
                        "description": "New file path",
                    },
                },
                "required": ["old_path", "new_path"],
            },
        },
    },
]


async def execute_app_tool(
    tool_name: str,
    arguments: dict[str, Any],
    app_id: str,
    branch_id: str,
    db: Session,
) -> dict[str, Any]:
    """Execute one of the app-scoped tools. Returns {ok, result, error}."""
    import uuid as _uuid

    try:
        app_uuid = _uuid.UUID(str(app_id))
        branch_uuid = _uuid.UUID(str(branch_id))
    except ValueError as e:
        return {"ok": False, "error": str(e), "result": {}}

    try:
        from app.apps.services.file_service import (
            read_file as _read_file,
            write_file as _write_file,
            list_files as _list_files,
            delete_file as _delete_file,
        )
    except ImportError as exc:
        logger.error("Could not import file_service: %s", exc)
        return {"ok": False, "error": f"file_service unavailable: {exc}", "result": {}}

    try:
        if tool_name == "read_file":
            content = await _read_file(db, app_uuid, branch_uuid, arguments["path"])
            return {
                "ok": True,
                "result": {"content": content, "path": arguments["path"]},
                "error": None,
            }

        elif tool_name == "write_file":
            await _write_file(db, app_uuid, branch_uuid, arguments["path"], arguments["content"])
            return {
                "ok": True,
                "result": {"path": arguments["path"], "written": True},
                "error": None,
            }

        elif tool_name == "list_files":
            file_tree = await _list_files(db, app_uuid, branch_uuid)
            directory = arguments.get("directory", "")
            files = [
                {"path": f.path, "size_bytes": f.size_bytes, "status": f.status}
                for f in file_tree.files
                if not directory or f.path.startswith(directory)
            ]
            return {"ok": True, "result": {"files": files}, "error": None}

        elif tool_name == "delete_file":
            await _delete_file(db, app_uuid, branch_uuid, arguments["path"])
            return {
                "ok": True,
                "result": {"deleted": arguments["path"]},
                "error": None,
            }

        elif tool_name == "rename_file":
            # Implemented as read → write new → delete old (no native rename in file_service)
            old_path = arguments["old_path"]
            new_path = arguments["new_path"]
            content = await _read_file(db, app_uuid, branch_uuid, old_path)
            await _write_file(db, app_uuid, branch_uuid, new_path, content)
            await _delete_file(db, app_uuid, branch_uuid, old_path)
            return {
                "ok": True,
                "result": {"renamed": True, "from": old_path, "to": new_path},
                "error": None,
            }

        else:
            return {"ok": False, "error": f"Unknown tool: {tool_name}", "result": {}}

    except Exception as exc:
        logger.exception("App tool %s failed", tool_name)
        return {"ok": False, "error": str(exc), "result": {}}
