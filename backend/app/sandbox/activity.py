"""Read thinking and tool calls from a coding agent's own transcript.

Each agent keeps a different transcript. The parsers below are plain Python so
they can run inside the sandbox and be tested here without a live agent.
"""
from __future__ import annotations

import base64
import inspect
import json
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


def python_exec(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return f"python3 -c \"import base64; exec(base64.b64decode('{encoded}').decode())\""


def command_for(*functions, call: str) -> str:
    body = "\n".join(inspect.getsource(function) for function in functions)
    return python_exec(body + "\n" + call + "\n")


def format_tool_text(name, arguments, output=""):
    label = str(name or "tool").strip() or "tool"
    if isinstance(arguments, dict):
        detail = (
            arguments.get("command")
            or arguments.get("commandline")
            or arguments.get("command_line")
            or arguments.get("path")
            or arguments.get("file_path")
            or arguments.get("filePath")
            or arguments.get("pattern")
            or arguments.get("query")
            or arguments.get("toolsummary")
            or arguments.get("summary")
            or ""
        )
        if not detail and arguments:
            noise = {"waitmsbeforeasync", "wait_ms_before_async", "toolsummary", "summary"}
            kept = {key: value for key, value in arguments.items() if str(key).lower() not in noise}
            detail = json.dumps(kept or arguments, ensure_ascii=False)[:400]
    else:
        detail = str(arguments or "")
    lines = [label]
    detail = str(detail or "").strip()
    if detail:
        lines.append(detail[:500])
    output_text = str(output or "").strip()
    if output_text:
        lines.append(output_text[:800])
    return "\n".join(lines)


def activities_from_opencode_parts(rows):
    activities = []
    for part_id, message_json, part_json in rows:
        try:
            message = json.loads(message_json or "{}")
            part = json.loads(part_json or "{}")
        except json.JSONDecodeError:
            continue
        if message.get("role") != "assistant":
            continue
        part_type = part.get("type")
        if part_type == "reasoning":
            text = str(part.get("text") or "").strip()
            if text:
                activities.append({"kind": "thinking", "content": text, "source_id": str(part_id)})
            continue
        if part_type != "tool":
            continue
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        output = state.get("output") or state.get("error") or ""
        if isinstance(output, (dict, list)):
            output = json.dumps(output, ensure_ascii=False)
        activities.append(
            {
                "kind": "tool",
                "content": format_tool_text(part.get("tool"), state.get("input"), output),
                "source_id": str(part_id),
            }
        )
    return activities


def read_opencode_activities():
    import json
    import os
    import sqlite3

    path = "/root/.local/share/opencode/opencode.db"
    if not os.path.exists(path):
        return []
    connection = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        session = connection.execute(
            "SELECT id FROM session WHERE directory = '/workspace' ORDER BY time_updated DESC LIMIT 1"
        ).fetchone()
        if not session:
            return []
        rows = connection.execute(
            "SELECT p.id, m.data, p.data FROM part p "
            "JOIN message m ON p.message_id = m.id "
            "WHERE p.session_id = ? ORDER BY p.time_created",
            (session[0],),
        ).fetchall()
    finally:
        connection.close()
    return activities_from_opencode_parts(rows)


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


def opencode_activity_command() -> str:
    return command_for(
        format_tool_text,
        activities_from_opencode_parts,
        read_opencode_activities,
        call="import json; print(json.dumps(read_opencode_activities()))",
    )


def pi_activity_command() -> str:
    return command_for(
        format_tool_text,
        _block_text,
        activities_from_pi_entries,
        read_pi_activities,
        call="import json; print(json.dumps(read_pi_activities()))",
    )


def _request_text(content):
    import re

    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content or "", re.DOTALL)
    return " ".join(match.group(1).split()) if match else ""


def _plain_agent_text(text):
    import re

    return re.sub(r"\[([^\]]+)\]\((?:file://|https?://)[^)]+\)", r"\1", text or "").strip()


def _tool_output(content):
    lines = []
    for raw in (content or "").splitlines():
        line = " ".join(raw.split())
        if not line or line.startswith("Created At:") or line.startswith("Completed At:"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def activities_from_antigravity_steps(steps, conversation_id=""):
    """Turn an Antigravity transcript into tool calls and assistant replies."""
    activities = []
    requests = []
    anchor_index = -1
    pending_tool = None
    order_for_request = {}
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        step_index = step.get("step_index")
        step_type = str(step.get("type") or "")
        content = str(step.get("content") or "")
        if step_type == "USER_INPUT" or str(step.get("source") or "") == "USER_EXPLICIT":
            request = _request_text(content)
            pending_tool = None
            if not request:
                continue
            requests.append(request)
            anchor_index = len(requests) - 1
            continue
        if anchor_index < 0:
            continue
        thought = str(step.get("thinking") or "").strip()
        if thought:
            order_for_request[anchor_index] = order_for_request.get(anchor_index, 0) + 1
            activities.append(
                {
                    "kind": "thinking",
                    "content": thought,
                    "source_id": "agy:%s:%s:thinking" % (conversation_id, step_index),
                    "request_index": anchor_index,
                    "order": order_for_request[anchor_index],
                }
            )
        tool_calls = step.get("tool_calls") or []
        for offset, call in enumerate(tool_calls):
            if not isinstance(call, dict):
                continue
            args = call.get("args") if isinstance(call.get("args"), dict) else call.get("arguments")
            if isinstance(args, dict):
                args = {str(key).lower(): value for key, value in args.items()}
            order_for_request[anchor_index] = order_for_request.get(anchor_index, 0) + 1
            activities.append(
                {
                    "kind": "tool",
                    "content": format_tool_text(call.get("name"), args or {}),
                    "source_id": "agy:%s:%s:tool:%s" % (conversation_id, step_index, offset),
                    "request_index": anchor_index,
                    "order": order_for_request[anchor_index],
                }
            )
            pending_tool = len(activities) - 1
        lowered = step_type.lower()
        if not thought and ("think" in lowered or "reason" in lowered):
            text = _plain_agent_text(content)
            if text:
                order_for_request[anchor_index] = order_for_request.get(anchor_index, 0) + 1
                activities.append(
                    {
                        "kind": "thinking",
                        "content": text,
                        "source_id": "agy:%s:%s:thinking" % (conversation_id, step_index),
                        "request_index": anchor_index,
                        "order": order_for_request[anchor_index],
                    }
                )
            pending_tool = None
            continue
        if step_type in ("GENERIC", "TOOL_RESULT"):
            output = _tool_output(content)
            if pending_tool is not None and output and output not in activities[pending_tool]["content"]:
                activities[pending_tool]["content"] = (activities[pending_tool]["content"] + "\n" + output)[:1400]
            pending_tool = None
            continue
        text = _plain_agent_text(content)
        if text and str(step.get("source") or "") == "MODEL":
            order_for_request[anchor_index] = order_for_request.get(anchor_index, 0) + 1
            activities.append(
                {
                    "kind": "reply",
                    "content": text,
                    "source_id": "agy:%s:%s:reply" % (conversation_id, step_index),
                    "request_index": anchor_index,
                    "order": order_for_request[anchor_index],
                }
            )
            pending_tool = None
    return {"activities": activities, "requests": requests}


def antigravity_conversation_score(steps, user_texts):
    """How many of this conversation's prompts also belong to the open session."""
    wanted = [" ".join(str(item).split()) for item in (user_texts or []) if str(item).strip()]
    score = 0
    pool = list(wanted)
    for step in steps or []:
        if not isinstance(step, dict) or str(step.get("type") or "") != "USER_INPUT":
            continue
        request = _request_text(str(step.get("content") or ""))
        if request and request in pool:
            pool.remove(request)
            score += 1
    return score


def _antigravity_transcript_path(folder):
    import os

    path = os.path.join(folder, ".system_generated", "logs", "transcript_full.jsonl")
    if os.path.isfile(path):
        return path
    path = os.path.join(folder, ".system_generated", "logs", "transcript.jsonl")
    if os.path.isfile(path):
        return path
    return ""


def _load_antigravity_steps(path):
    import json

    steps = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return steps


def read_antigravity_activities(user_texts, session_id=""):
    import os

    roots = (
        "/root/.gemini/antigravity-cli/brain",
        "/root/.gemini/antigravity/brain",
    )
    session_id = str(session_id or "").strip()
    if session_id:
        marker = os.path.join("/root/.gemini/sessions", "%s.conv_id" % session_id)
        conv_id = ""
        if os.path.isfile(marker):
            with open(marker, encoding="utf-8", errors="replace") as handle:
                conv_id = handle.read().strip()
        if not conv_id:
            return {"activities": [], "requests": []}
        for root in roots:
            path = _antigravity_transcript_path(os.path.join(root, conv_id))
            if path:
                return activities_from_antigravity_steps(_load_antigravity_steps(path), conv_id)
        return {"activities": [], "requests": []}
    best_steps = None
    best_id = ""
    best_score = 0
    best_mtime = -1
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            path = _antigravity_transcript_path(os.path.join(root, name))
            if not path:
                continue
            steps = _load_antigravity_steps(path)
            score = antigravity_conversation_score(steps, user_texts)
            if score <= 0:
                continue
            modified = os.path.getmtime(path)
            if score > best_score or (score == best_score and modified > best_mtime):
                best_steps = steps
                best_id = name
                best_score = score
                best_mtime = modified
    if not best_steps:
        return {"activities": [], "requests": []}
    return activities_from_antigravity_steps(best_steps, best_id)


def antigravity_activity_command(user_texts, session_id=None) -> str:
    cleaned = []
    for text in user_texts or []:
        item = " ".join(str(text).split())
        if item:
            cleaned.append(item[:500])
    payload = json.dumps(cleaned[-30:])
    session_payload = json.dumps(str(session_id or ""))
    return command_for(
        format_tool_text,
        _request_text,
        _plain_agent_text,
        _tool_output,
        activities_from_antigravity_steps,
        antigravity_conversation_score,
        _antigravity_transcript_path,
        _load_antigravity_steps,
        read_antigravity_activities,
        call="import json; print(json.dumps(read_antigravity_activities(%s, %s)))" % (payload, session_payload),
    )


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
