from __future__ import annotations

import base64
import inspect
import json

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

