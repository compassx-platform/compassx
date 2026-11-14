from __future__ import annotations

import json

from app.sandbox.activity_sources.support import command_for, format_tool_text

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

