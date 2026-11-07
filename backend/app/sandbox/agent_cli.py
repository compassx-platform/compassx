"""Shared coding-agent CLI and tmux commands for sandbox terminals and Agent Runtime."""
from __future__ import annotations

import base64
import shlex

SHELL_AGENTS = frozenset({"bash", "shell", "sh"})
DEFAULT_WORKDIR = "/workspace"


def tmux_session_name(session_id: str) -> str:
    return f"cx_{session_id.replace('-', '_')}"


def agent_inner_command(agent: str, session_id: str | None) -> str:
    """Shell command that execs the selected coding agent, or a login shell."""
    from app.sandbox.agents import agent_registry

    resolved = (agent or "").lower().strip()
    if resolved in ("agy",):
        resolved = "antigravity"
    elif resolved in ("compassx", "compass"):
        resolved = "nova"
    elif resolved in ("claude-code", "claudecode"):
        resolved = "claude"
    elif resolved in ("cursor-agent", "cursorcli"):
        resolved = "cursor"
    adapter = agent_registry.get(resolved)
    if adapter:
        return adapter.launch_command(session_id)
    return "if [ -x /bin/bash ]; then exec /bin/bash -l; else exec /bin/sh -l; fi"


def tmux_scroll_setup_shell() -> str:
    """Make mouse-wheel scrolling work for a sandbox tmux server."""
    return (
        "touch /root/.tmux.conf; "
        "grep -q 'mouse on' /root/.tmux.conf || printf '\\nset -g mouse on\\nset -g history-limit 50000\\n' >> /root/.tmux.conf; "
        "tmux set-option -g mouse on >/dev/null 2>&1 || true; "
        "tmux set-option -g history-limit 50000 >/dev/null 2>&1 || true; "
    )


def interactive_shell_command(
    agent: str | None,
    session_id: str | None,
    workdir: str,
    command: str | None = None,
) -> str:
    """PTY command. Coding agents attach to a named tmux session when a session id is set."""
    resolved = (agent or "").lower().strip()
    cli_cmd = command or agent_inner_command(resolved or "bash", session_id)
    if session_id and resolved and resolved not in SHELL_AGENTS:
        tmux_target = tmux_session_name(session_id)
        clean_cmd = cli_cmd.replace("'", "'\\''")
        fallback = command or agent_inner_command(resolved, session_id)
        cli_cmd = (
            f"{tmux_scroll_setup_shell()}"
            f"(which tmux >/dev/null 2>&1 && tmux new-session -A -D -s '{tmux_target}' -c '{workdir}' '{clean_cmd}' "
            f"\\; set-option -g status off \\; set-option -g mouse on \\; set-option -g history-limit 50000 \\; set-option -w window-size latest "
            f"|| exec /bin/bash -l) "
            f"|| ( {fallback} )"
        )
    return cli_cmd


def detached_start_command(agent: str, session_id: str, workdir: str = DEFAULT_WORKDIR) -> str:
    """Start the agent in tmux if that session does not already exist."""
    name = shlex.quote(tmux_session_name(session_id))
    directory = shlex.quote(workdir or DEFAULT_WORKDIR)
    inner = agent_inner_command(agent, session_id).replace("'", "'\\''")
    return (
        "command -v tmux >/dev/null 2>&1 || { echo 'tmux is not installed in this sandbox' >&2; exit 127; }; "
        f"if ! tmux has-session -t {name} 2>/dev/null; then "
        f"tmux new-session -d -s {name} -c {directory} '{inner}' || tmux has-session -t {name}; "
        f"fi; "
        f"tmux set-option -g status off; "
        f"tmux set-option -g mouse on; "
        f"tmux set-option -g history-limit 50000"
    )


def pane_capture_command(session_id: str, history_lines: int = 40) -> str:
    name = shlex.quote(tmux_session_name(session_id))
    lines = max(1, int(history_lines))
    return f"tmux capture-pane -p -t {name} -S -{lines}"


def pane_log_path(session_id: str) -> str:
    return f"/tmp/{tmux_session_name(session_id)}.log"


def ensure_pane_log_command(session_id: str) -> str:
    """Append new terminal output to a log so errors survive a full-screen redraw."""
    name = shlex.quote(tmux_session_name(session_id))
    path = shlex.quote(pane_log_path(session_id))
    return f"tmux pipe-pane -o -t {name} 'cat >> {path}'"


def read_pane_log_command(session_id: str) -> str:
    path = shlex.quote(pane_log_path(session_id))
    return f"tail -c 200000 {path} 2>/dev/null || true"


def deliver_prompt_command(session_id: str, prompt: str) -> str:
    """Paste a prompt into the tmux pane and submit it."""
    name = shlex.quote(tmux_session_name(session_id))
    encoded = shlex.quote(base64.b64encode(prompt.encode("utf-8")).decode("ascii"))
    # Leave copy mode first. A scroll in the attached terminal puts tmux there,
    # and then Enter never reaches the agent, so chat waits forever.
    return (
        f"tmux copy-mode -q -t {name} 2>/dev/null || true; "
        f"printf '%s' {encoded} | base64 -d | tmux load-buffer - && "
        f"tmux paste-buffer -t {name} && "
        f"sleep 0.2 && "
        f"tmux send-keys -t {name} Enter"
    )
