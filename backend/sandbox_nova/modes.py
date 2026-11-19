"""Per-turn mode gate. Agent may change files. The other modes may not."""

from __future__ import annotations

from typing import Any

MODES = ("agent", "ask", "plan", "debug")

_READ_ONLY = frozenset({
    "list_files",
    "read_file",
    "search_assets",
    "catalog",
    "rag_search",
})


def normalize_mode(value: str | None) -> str:
    mode = (value or "").strip().lower()
    return mode if mode in MODES else "agent"


def allowed_tool_names(mode: str | None) -> frozenset[str] | None:
    """None means every registered tool. A set is the only tools that mode may call."""
    selected = normalize_mode(mode)
    if selected == "agent":
        return None
    if selected == "plan":
        return _READ_ONLY | {"write_plan"}
    if selected == "debug":
        return _READ_ONLY | {"run_shell", "python_code"}
    return _READ_ONLY


def tool_definitions(tools: list[dict[str, Any]], mode: str | None) -> list[dict[str, Any]]:
    allowed = allowed_tool_names(mode)
    if allowed is None:
        return tools
    return [item for item in tools if ((item.get("function") or {}).get("name") in allowed)]


def mode_prompt(mode: str | None) -> str:
    selected = normalize_mode(mode)
    if selected == "ask":
        return (
            "You are in Ask mode. Answer from files and read-only platform tools. "
            "Do not change files, run commands, or call a write tool."
        )
    if selected == "plan":
        return (
            "You are in Plan mode. Research first, then call write_plan once with a kebab-case name "
            "and the full markdown. Do not change any other file and do not start the work. "
            "After the Thought block, the reply is that same plan."
        )
    if selected == "debug":
        return (
            "You are in Debug mode. State the hypotheses, then gather evidence with read and run tools. "
            "Do not change files or call a write tool. After the Thought block, the reply is the evidence."
        )
    return ""


def reply_kind(mode: str | None) -> str:
    selected = normalize_mode(mode)
    if selected == "plan":
        return "plan"
    if selected == "debug":
        return "debug"
    return "reply"
