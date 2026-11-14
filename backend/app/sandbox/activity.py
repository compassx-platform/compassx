"""Read thinking and tool calls from a coding agent's own transcript.

Each agent keeps a different transcript. The parsers below are plain Python so
they can run inside the sandbox and be tested here without a live agent.
"""
from app.sandbox.activity_sources.antigravity import (
    _antigravity_transcript_path,
    _load_antigravity_steps,
    _plain_agent_text,
    _request_text,
    _tool_output,
    activities_from_antigravity_steps,
    antigravity_activity_command,
    antigravity_conversation_score,
    read_antigravity_activities,
)
from app.sandbox.activity_sources.opencode import (
    activities_from_opencode_parts,
    opencode_activity_command,
    read_opencode_activities,
)
from app.sandbox.activity_sources.pane import (
    _ANSI,
    _TOOL_HEADERS,
    _is_chrome,
    _is_prompt_line,
    _starts_new_block,
    _visible_line,
    activities_from_pane,
)
from app.sandbox.activity_sources.pi import (
    _block_text,
    activities_from_pi_entries,
    pi_activity_command,
    read_pi_activities,
)
from app.sandbox.activity_sources.support import command_for, format_tool_text, python_exec

__all__ = [
    "_ANSI",
    "_TOOL_HEADERS",
    "_antigravity_transcript_path",
    "_block_text",
    "_is_chrome",
    "_is_prompt_line",
    "_load_antigravity_steps",
    "_plain_agent_text",
    "_request_text",
    "_starts_new_block",
    "_tool_output",
    "_visible_line",
    "activities_from_antigravity_steps",
    "activities_from_opencode_parts",
    "activities_from_pane",
    "activities_from_pi_entries",
    "antigravity_activity_command",
    "antigravity_conversation_score",
    "command_for",
    "format_tool_text",
    "opencode_activity_command",
    "pi_activity_command",
    "python_exec",
    "read_antigravity_activities",
    "read_opencode_activities",
    "read_pi_activities",
]
