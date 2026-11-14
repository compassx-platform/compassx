from __future__ import annotations

import re

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_TOOL_HEADERS = {
    "bash",
    "read",
    "edit",
    "write",
    "grep",
    "glob",
    "webfetch",
    "task",
    "todowrite",
    "skill",
}

def activities_from_pane(text: str) -> list[dict[str, str]]:
    """Pick labeled thinking and tool lines out of a terminal capture."""
    lines = []
    for raw in (text or "").splitlines():
        line = _visible_line(raw)
        if line and not _is_chrome(line):
            lines.append(line)
    activities: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lower().startswith("thinking:"):
            chunk = [line.split(":", 1)[1].strip()]
            index += 1
            while index < len(lines) and not _starts_new_block(lines[index]):
                chunk.append(lines[index])
                index += 1
            content = "\n".join(part for part in chunk if part).strip()
            if content:
                activities.append({"kind": "thinking", "content": content, "source_id": "pane:thinking:" + content[:180]})
            continue
        head = line.split(" ", 1)[0].lower().rstrip(":")
        if head in _TOOL_HEADERS:
            rest = line[len(line.split(" ", 1)[0]) :].strip()
            index += 1
            if not rest and index < len(lines) and not _is_prompt_line(lines[index]) and not _starts_new_block(lines[index]):
                rest = lines[index]
                index += 1
            if rest:
                content = head + "\n" + rest
                activities.append({"kind": "tool", "content": content, "source_id": "pane:tool:" + content[:180]})
            continue
        index += 1
    return activities


def _visible_line(raw: str) -> str:
    line = _ANSI.sub("", raw or "")
    for mark in ("┃", "│", "║", "█", "▓", "▒", "░", "▀", "▄", "▌", "▐", "╹", "╻"):
        line = line.replace(mark, " ")
    return " ".join(line.split())


def _is_chrome(line: str) -> bool:
    if re.fullmatch(r"[\W_]+", line):
        return True
    lowered = line.lower()
    if lowered.startswith("/workspace") or lowered.startswith("tab agents") or "ctrl+p" in lowered:
        return True
    if lowered.startswith("build ·") or lowered.startswith("▣"):
        return True
    return False


def _is_prompt_line(line: str) -> bool:
    return len(line) <= 24 and line.count(" ") <= 2 and not line.lower().startswith("thinking:")


def _starts_new_block(line: str) -> bool:
    if line.lower().startswith("thinking:"):
        return True
    head = line.split(" ", 1)[0].lower().rstrip(":")
    return head in _TOOL_HEADERS

