# Coding agents

The sandbox module does not expose an agent-tool HTTP route. Agent runtime asks this module which agents can be launched and how to read their transcripts.

`app.sandbox.agents` keeps `agent_registry`, `is_nova_agent`, `is_cli_agent`, and `extract_terminal_notices`. The registry holds one class per agent: Nova, Antigravity, Pi, OpenCode, Claude Code, Codex, and Cursor. `catalog()` returns those ids and labels. A new agent is registered on the same registry. Callers do not change the import path.

`app.sandbox.agent_cli` builds the tmux text those classes share: the inner command, the detached start, the pane capture, and the prompt delivery. Drivers call `interactive_shell_command` from this module.

`app.sandbox.activity` keeps every parser name that callers already import. The functions are defined under `activity_sources/`, one file per transcript family:

- `support.py` — `python_exec`, `command_for`, and `format_tool_text`
- `opencode.py` — OpenCode
- `pi.py` — Pi
- `antigravity.py` — Antigravity
- `pane.py` — text scraped from a terminal pane

`command_for` still concatenates the source of the functions it is given and runs that source inside the sandbox. The activity command for each agent passes the same functions it passed before.

Nova's in-sandbox process is the separate package `sandbox_nova`. `loop.py` keeps `NovaAgentLoop` and re-exports `InboxServer` from `inbox.py`. Each local tool class stays importable from `sandbox_nova.tools.local` and is defined under `sandbox_nova/tools/builtin/`. Platform tools stay in `sandbox_nova/tools/platform.py` and call back to the agent-runtime tool route.
