from __future__ import annotations

import json

from app.sandbox.activity_sources.support import command_for, format_tool_text

def _block_text(content):
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    chunks = []
    for block in content:
        if isinstance(block, str):
            chunks.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text") or ""))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def activities_from_pi_entries(entries):
    activities = []
    tool_index = {}
    for entry in entries:
        message = entry.get("message") if isinstance(entry, dict) else None
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        entry_id = str(entry.get("id") or "")
        if role == "assistant":
            for offset, block in enumerate(message.get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "thinking":
                    text = str(block.get("thinking") or "").strip()
                    if text:
                        activities.append(
                            {"kind": "thinking", "content": text, "source_id": "%s:thinking:%s" % (entry_id, offset)}
                        )
                elif block.get("type") == "toolCall":
                    call_id = str(block.get("id") or "%s:tool:%s" % (entry_id, offset))
                    activities.append(
                        {
                            "kind": "tool",
                            "content": format_tool_text(block.get("name"), block.get("arguments")),
                            "source_id": call_id,
                        }
                    )
                    tool_index[call_id] = len(activities) - 1
        elif role == "toolResult":
            call_id = str(message.get("toolCallId") or "")
            output = _block_text(message.get("content"))
            if message.get("isError") and output:
                output = "Error: " + output
            if call_id in tool_index and output:
                current = activities[tool_index[call_id]]
                if output not in current["content"]:
                    current["content"] = (current["content"] + "\n" + output)[:1400]
    return activities


def read_pi_activities():
    import json
    import os

    root = os.path.expanduser("~/.pi/agent/sessions")
    newest = ""
    newest_mtime = -1
    if os.path.isdir(root):
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                if not name.endswith(".jsonl"):
                    continue
                path = os.path.join(dirpath, name)
                modified = os.path.getmtime(path)
                if modified > newest_mtime:
                    newest = path
                    newest_mtime = modified
    if not newest:
        return []
    entries = []
    with open(newest, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return activities_from_pi_entries(entries)


def pi_activity_command() -> str:
    return command_for(
        format_tool_text,
        _block_text,
        activities_from_pi_entries,
        read_pi_activities,
        call="import json; print(json.dumps(read_pi_activities()))",
    )

