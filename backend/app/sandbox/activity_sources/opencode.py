from __future__ import annotations

import json

from app.sandbox.activity_sources.support import command_for, format_tool_text

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


def opencode_activity_command() -> str:
    return command_for(
        format_tool_text,
        activities_from_opencode_parts,
        read_opencode_activities,
        call="import json; print(json.dumps(read_opencode_activities()))",
    )

