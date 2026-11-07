"""Coding-agent adapters for Agent Runtime.

Add a new agent by subclassing TmuxCodingAgent and registering it.
The terminal and chat surfaces call the registry; they do not branch on agent names.
"""
from __future__ import annotations

import re
from typing import Protocol

_ERROR_HINT = re.compile(
    r"error|failed|forbidden|exception|traceback|blocked|denied|unauthorized|invalid",
    re.IGNORECASE,
)
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
NOVA_AGENT_IDS = frozenset({"nova", "compassx", "compass"})


def is_nova_agent(agent_type: str | None) -> bool:
    return (agent_type or "").lower().strip() in NOVA_AGENT_IDS


def is_cli_agent(agent_type: str | None) -> bool:
    value = (agent_type or "").lower().strip()
    return bool(value) and value not in NOVA_AGENT_IDS


def extract_terminal_notices(pane_text: str) -> list[str]:
    """Pull readable error text out of a tmux pane, skipping agent chrome."""
    lines = [_visible_line(line) for line in (pane_text or "").splitlines()]
    lines = [line for line in lines if line and not _is_chrome(line)]
    notices: list[str] = []
    index = 0
    while index < len(lines):
        if not _ERROR_HINT.search(lines[index]):
            index += 1
            continue
        chunk = [lines[index]]
        index += 1
        while index < len(lines) and not _is_prompt_line(lines[index]):
            if _ERROR_HINT.search(lines[index]):
                break
            chunk.append(lines[index])
            index += 1
        notice = "\n".join(chunk).strip()
        if notice:
            notices.append(notice)
    return notices


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
    return len(line) <= 24 and line.count(" ") <= 2 and not _ERROR_HINT.search(line)


class CodingAgent(Protocol):
    id: str
    label: str

    def launch_command(self, session_id: str | None) -> str:
        """Shell command that starts this agent inside the sandbox."""

    def deliver_command(self, session_id: str, prompt: str) -> str:
        """Shell command that submits a prompt to a running agent."""

    def extract_notices(self, pane_text: str) -> list[str]:
        """Error text from this agent's terminal that should appear in chat."""

    def activity_command(self, user_texts: list[str] | None = None, session_id: str | None = None) -> str | None:
        """Shell command that prints this session's thinking, tools, and replies as JSON."""


class AgentRegistry:
    """Maps an agent id to the adapter that knows how to run it."""

    def __init__(self) -> None:
        self._agents: dict[str, CodingAgent] = {}

    def register(self, agent: CodingAgent) -> None:
        agent_id = (agent.id or "").lower().strip()
        if not agent_id:
            raise ValueError("Agent id is required.")
        self._agents[agent_id] = agent

    def get(self, agent_id: str | None) -> CodingAgent | None:
        return self._agents.get((agent_id or "").lower().strip())

    def catalog(self) -> list[dict[str, str]]:
        return [{"id": agent.id, "label": agent.label} for agent in self._agents.values()]


class TmuxCodingAgent:
    """Default prompt delivery: paste into the agent's tmux session."""

    id = ""
    label = ""

    def launch_command(self, session_id: str | None) -> str:
        raise NotImplementedError

    def deliver_command(self, session_id: str, prompt: str) -> str:
        from app.sandbox.agent_cli import deliver_prompt_command

        return deliver_prompt_command(session_id, prompt)

    def extract_notices(self, pane_text: str) -> list[str]:
        return extract_terminal_notices(pane_text)

    def activity_command(self, user_texts: list[str] | None = None, session_id: str | None = None) -> str | None:
        return None


class NovaAgent(TmuxCodingAgent):
    id = "nova"
    label = "Nova"

    def launch_command(self, session_id: str | None) -> str:
        sid = session_id or ""
        return (
            "set -a; "
            "[ -f /run/compassx/nova.env ] && . /run/compassx/nova.env; "
            "set +a; "
            f"export NOVA_SESSION_ID='{sid}' NOVA_WORKSPACE=/workspace; "
            "if command -v nova >/dev/null 2>&1; then exec nova serve --session \"$NOVA_SESSION_ID\"; fi; "
            "export PYTHONPATH=/opt/compassx:${PYTHONPATH:-}; "
            "if python3 -c 'import sandbox_nova' >/dev/null 2>&1; then exec python3 -m sandbox_nova serve --session \"$NOVA_SESSION_ID\"; fi; "
            "echo 'Nova CLI is not installed in this sandbox. Rebuild compassx-sandbox-host.' >&2; "
            "exec /bin/bash -l"
        )

    def activity_command(self, user_texts: list[str] | None = None, session_id: str | None = None) -> str | None:
        sid = session_id or ""
        return (
            f"PYTHONPATH=/opt/compassx:${{PYTHONPATH:-}} nova transcript --session '{sid}' 2>/dev/null || "
            f"PYTHONPATH=/opt/compassx python3 -m sandbox_nova transcript --session '{sid}'"
        )


class AntigravityAgent(TmuxCodingAgent):
    id = "antigravity"
    label = "Antigravity"

    def launch_command(self, session_id: str | None) -> str:
        sess_f = f"/root/.gemini/sessions/{session_id}.conv_id" if session_id else ""
        return (
            "export AGY_TRUST_ALL=true ANTIGRAVITY_TRUST_ALL_WORKSPACES=true AGY_NON_INTERACTIVE=true; "
            "mkdir -p /root/.gemini/sessions /root/.gemini/antigravity-cli/brain /root/.gemini/antigravity/brain; "
            f"if [ -n \"{sess_f}\" ] && [ -f \"{sess_f}\" ] && [ -n \"$(cat '{sess_f}' 2>/dev/null)\" ]; then "
            f"  exec agy --dangerously-skip-permissions --conversation \"$(cat '{sess_f}')\"; "
            f"else "
            "  KNOWN=$(ls -1d /root/.gemini/antigravity-cli/brain/*/ /root/.gemini/antigravity/brain/*/ 2>/dev/null); "
            "  (for _i in $(seq 1 20); do "
            "     sleep 1; "
            "     for d in /root/.gemini/antigravity-cli/brain/*/ /root/.gemini/antigravity/brain/*/; do "
            "       [ -d \"$d\" ] || continue; "
            "       case \"$KNOWN\" in "
            "         *\"$d\"*) ;; "
            "         *) "
            "           NEW_ID=$(basename \"$d\"); "
            f"           if [ -n \"$NEW_ID\" ] && [ -n \"{sess_f}\" ]; then echo \"$NEW_ID\" > '{sess_f}'; break 2; fi; "
            "           ;; "
            "       esac; "
            "     done; "
            "   done) & "
            "  exec agy --dangerously-skip-permissions; "
            "fi"
        )

    def activity_command(self, user_texts: list[str] | None = None, session_id: str | None = None) -> str | None:
        from app.sandbox.activity import antigravity_activity_command

        return antigravity_activity_command(user_texts or [], session_id)


class PiAgent(TmuxCodingAgent):
    id = "pi"
    label = "Pi"

    def launch_command(self, session_id: str | None) -> str:
        return "pi --approve"

    def activity_command(self, user_texts: list[str] | None = None, session_id: str | None = None) -> str | None:
        from app.sandbox.activity import pi_activity_command

        return pi_activity_command()


class OpenCodeAgent(TmuxCodingAgent):
    id = "opencode"
    label = "OpenCode"

    def launch_command(self, session_id: str | None) -> str:
        return "opencode"

    def activity_command(self, user_texts: list[str] | None = None, session_id: str | None = None) -> str | None:
        from app.sandbox.activity import opencode_activity_command

        return opencode_activity_command()


class ClaudeCodeAgent(TmuxCodingAgent):
    id = "claude"
    label = "Claude Code"

    def launch_command(self, session_id: str | None) -> str:
        return "claude --dangerously-skip-permissions"


class CodexAgent(TmuxCodingAgent):
    id = "codex"
    label = "Codex"

    def launch_command(self, session_id: str | None) -> str:
        return "codex --dangerously-bypass-approvals-and-sandbox"


class CursorAgent(TmuxCodingAgent):
    id = "cursor"
    label = "Cursor"

    def launch_command(self, session_id: str | None) -> str:
        return (
            "if command -v cursor-agent >/dev/null 2>&1; then "
            "exec cursor-agent --force; "
            "elif command -v agent >/dev/null 2>&1; then "
            "exec agent --force; "
            "else "
            "echo 'Cursor CLI is not installed in this sandbox' >&2; "
            "exec /bin/bash -l; "
            "fi"
        )


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(NovaAgent())
    registry.register(AntigravityAgent())
    registry.register(PiAgent())
    registry.register(OpenCodeAgent())
    registry.register(ClaudeCodeAgent())
    registry.register(CodexAgent())
    registry.register(CursorAgent())
    return registry


agent_registry = build_default_registry()
