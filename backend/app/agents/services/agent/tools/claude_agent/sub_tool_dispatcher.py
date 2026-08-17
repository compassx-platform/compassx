"""Sub-tool dispatcher for the agentic loop.

Builds the OpenAI-style tool definitions list and a dispatch function that
routes each tool call to the correct provider or file-system operation.

To add a new sub-tool:
  1. Add its JSON schema to ``build_sub_tools()``.
  2. Add its dispatch branch to ``build_dispatch_fn()``.
  No other files need to change.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.models.agents import Agent
from app.agents.services.agent.tools.auth.pat_resolver import get_pat
from app.agents.services.agent.tools.providers import get_provider

logger = logging.getLogger(__name__)


def build_sub_tools() -> list[dict[str, Any]]:
    """Return OpenAI function-calling definitions for all sub-tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "create_pr",
                "description": "Create a pull request on GitHub or Azure DevOps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "branch": {"type": "string"},
                        "base_branch": {"type": "string"},
                        "repo": {"type": "string"},
                        "organization": {"type": "string"},
                        "project": {"type": "string"},
                        "provider": {"type": "string", "enum": ["github", "azure_devops"]},
                        "draft": {"type": "boolean"},
                    },
                    "required": ["title", "branch", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "post_pr_comment",
                "description": "Post a comment on a pull request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "pr_number": {"type": "integer"},
                        "repo": {"type": "string"},
                        "organization": {"type": "string"},
                        "project": {"type": "string"},
                        "provider": {"type": "string", "enum": ["github", "azure_devops"]},
                    },
                    "required": ["message", "pr_number", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_pr_ready",
                "description": "Mark a pull request as ready for review (remove draft status).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pr_number": {"type": "integer"},
                        "repo": {"type": "string"},
                        "organization": {"type": "string"},
                        "project": {"type": "string"},
                        "provider": {"type": "string", "enum": ["github", "azure_devops"]},
                    },
                    "required": ["pr_number", "repo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "post_workitem_comment",
                "description": "Post a comment on an Azure DevOps work item or GitHub issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "workitem_id": {"type": "integer"},
                        "repo": {"type": "string"},
                        "organization": {"type": "string"},
                        "project": {"type": "string"},
                        "provider": {"type": "string", "enum": ["github", "azure_devops"]},
                    },
                    "required": ["message", "workitem_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_workitem_status",
                "description": "Update the status/state of an Azure DevOps work item or GitHub issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workitem_id": {"type": "integer"},
                        "state": {"type": "string"},
                        "repo": {"type": "string"},
                        "organization": {"type": "string"},
                        "project": {"type": "string"},
                        "provider": {"type": "string", "enum": ["github", "azure_devops"]},
                    },
                    "required": ["workitem_id", "state"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_multiple_files",
                "description": (
                    "Read the contents of multiple files in one call. "
                    "More efficient than calling read_file N times. "
                    "Returns a JSON object mapping each path to its content (or an error string)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of absolute or relative file paths to read.",
                        }
                    },
                    "required": ["paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a single file from the git worktree.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or relative path to the file."},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write or overwrite a file in the git worktree.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files and folders in a directory of the git worktree.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list. Defaults to worktree root.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_commit_and_push",
                "description": "Stage all changes, commit with a message, and push the branch to origin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Commit message."},
                    },
                    "required": ["message"],
                },
            },
        },
    ]


def build_dispatch_fn(agent: Agent, outer_args: dict[str, Any]):
    """Return a dispatch function bound to *agent* and *outer_args*.

    The returned callable has signature ``(tool_name: str, tool_args: dict) -> str``
    and returns a JSON string suitable for appending as a tool result message.
    """

    def _dispatch(tool_name: str, tool_args: dict) -> str:
        provider_name = tool_args.get("provider") or outer_args.get("provider", "github")

        # Inherit repo/org/project from the parent call when not explicitly provided
        for key in ("repo", "organization", "project", "base_branch"):
            if key not in tool_args and key in outer_args:
                tool_args[key] = outer_args[key]

        git_worktree_path = outer_args.get("worktree_path", "")

        token = get_pat(agent, provider_name)
        logger.debug(
            "_dispatch %s — provider=%s pat=%s",
            tool_name, provider_name, "set" if token else "NOT SET",
        )

        try:
            # ── Provider-delegated operations ─────────────────────────────────
            if tool_name in ("create_pr", "post_pr_comment", "set_pr_ready",
                             "post_workitem_comment", "update_workitem_status"):
                provider = get_provider(provider_name)
                method = getattr(provider, {
                    "create_pr": "create_pr",
                    "post_pr_comment": "post_pr_comment",
                    "set_pr_ready": "set_pr_ready",
                    "post_workitem_comment": "post_workitem_comment",
                    "update_workitem_status": "update_workitem_status",
                }[tool_name])
                return json.dumps(method(tool_args, token))

            # ── File-system operations ────────────────────────────────────────
            elif tool_name == "read_multiple_files":
                file_results = {}
                for raw_path in tool_args.get("paths", []):
                    resolved = raw_path
                    if not os.path.isabs(raw_path) and git_worktree_path:
                        resolved = os.path.join(git_worktree_path, raw_path)
                    try:
                        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                            file_results[raw_path] = f.read()[:20000]  # 20 k cap per file
                    except Exception as exc:
                        file_results[raw_path] = f"# Error reading file: {exc}"
                return json.dumps(file_results)

            elif tool_name == "read_file":
                path = tool_args["path"]
                if not os.path.isabs(path) and git_worktree_path:
                    path = os.path.join(git_worktree_path, path)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                return content[:50000]

            elif tool_name == "write_file":
                path = tool_args["path"]
                if not os.path.isabs(path) and git_worktree_path:
                    path = os.path.join(git_worktree_path, path)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(tool_args["content"])
                return json.dumps({"ok": True, "path": path})

            elif tool_name == "list_directory":
                path = tool_args.get("path", git_worktree_path or ".")
                if not os.path.isabs(path) and git_worktree_path:
                    path = os.path.join(git_worktree_path, path)
                path = str(Path(path).resolve())
                if not os.path.isdir(path):
                    return json.dumps({"error": f"Not a directory: {path}"})
                entries = []
                for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name)):
                    if not entry.is_dir(follow_symlinks=False) and not entry.is_file(follow_symlinks=False):
                        continue
                    entries.append(("dir" if entry.is_dir() else "file") + "  " + entry.name)
                return "\n".join(entries)

            elif tool_name == "git_commit_and_push":
                import subprocess as _sp

                cwd = git_worktree_path or "."
                msg = tool_args.get("message", "chore: automated commit")
                cmds = [
                    ["git", "add", "-A"],
                    ["git", "commit", "-m", msg],
                    ["git", "push", "--set-upstream", "origin", "HEAD"],
                ]
                output_parts = []
                for cmd in cmds:
                    r = _sp.run(cmd, cwd=cwd, capture_output=True, text=True)
                    output_parts.append(f"$ {' '.join(cmd)}\n{r.stdout}{r.stderr}".strip())
                    if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
                        return json.dumps({"ok": False, "error": r.stderr or r.stdout, "cmd": cmd})
                return json.dumps({"ok": True, "output": "\n".join(output_parts)})

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as exc:
            logger.exception("Sub-tool %s failed", tool_name)
            return json.dumps({"error": str(exc)})

    return _dispatch
