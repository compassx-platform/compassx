"""LLM invocation helpers for ClaudeAgentTool.

Three strategies are available:
  - ask_claude_text         : single-turn text generation via chat_stream
  - invoke_via_llm_connection : multi-turn agentic loop with tool dispatch
  - invoke_claude_cli       : one-shot Claude Code CLI subprocess
  - invoke_claude_sdk       : Claude Agent SDK (MCP server)

The orchestrator (ClaudeAgentTool) calls ``invoke_via_llm_connection``
(aliased as ``invoke_claude``) as the primary path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from typing import Any

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import ToolResult

logger = logging.getLogger(__name__)


def _get_llm_connection(agent: Agent):
    return getattr(agent, "llm_connection", None)


# ── Single-turn text generation ───────────────────────────────────────────────

def ask_claude_text(prompt: str, agent: Agent) -> ToolResult:
    """Generate text using the agent's configured LLM connection (no tools)."""
    conn = _get_llm_connection(agent)
    if conn is None:
        return ToolResult(ok=False, error="Agent has no LLM connection configured")

    try:
        from app.services.llm_client import chat_stream

        output_chunks: list[str] = []

        async def _collect():
            async for event in chat_stream(
                conn=conn,
                messages=[{"role": "user", "content": prompt}],
            ):
                if event["type"] == "text":
                    output_chunks.append(event["delta"])

        asyncio.run(_collect())
        return ToolResult(ok=True, result={"output": "".join(output_chunks)})
    except Exception as exc:
        logger.exception("Claude text generation failed")
        return ToolResult(ok=False, error=str(exc))


# ── Multi-turn agentic loop ───────────────────────────────────────────────────

async def _invoke_via_llm_connection(
    prompt: str,
    sub_tools: list[dict],
    dispatch_fn,
    agent: Agent,
) -> ToolResult:
    """Run the agentic loop (up to 20 turns) using chat_stream.

    Args:
        prompt:      Initial user prompt.
        sub_tools:   OpenAI-style tool definitions list.
        dispatch_fn: Callable(tool_name, tool_args) -> str (JSON result).
        agent:       Agent ORM instance.
    """
    from app.services.llm_client import chat_stream

    conn = _get_llm_connection(agent)
    if conn is None:
        return ToolResult(ok=False, error="Agent has no LLM connection configured")

    messages: list[dict] = [{"role": "user", "content": prompt}]
    output_text = ""

    for turn in range(20):
        logger.debug("agentic loop turn %d", turn)
        tool_calls_received: list[dict] = []
        text_chunks: list[str] = []

        async for event in chat_stream(conn=conn, messages=messages, tools=sub_tools):
            if event["type"] == "text":
                text_chunks.append(event["delta"])
            elif event["type"] == "tool_use":
                tool_calls_received.extend(event["tool_calls"])

        turn_text = "".join(text_chunks)
        if turn_text:
            output_text += turn_text

        if not tool_calls_received:
            logger.debug("No tool calls on turn %d — done", turn)
            break

        # Omit "content" when empty — some providers reject null/empty assistant content
        # when tool_calls are present.
        assistant_msg: dict = {"role": "assistant"}
        if turn_text:
            assistant_msg["content"] = turn_text
        assistant_msg["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"]),
                },
            }
            for tc in tool_calls_received
        ]
        messages.append(assistant_msg)

        # Dispatch all tool calls in this turn concurrently.
        # Each dispatch_fn call is a blocking I/O operation (file read or network)
        # so we run them in a thread pool via run_in_executor.
        loop = asyncio.get_event_loop()
        dispatch_results = await asyncio.gather(
            *[
                loop.run_in_executor(None, dispatch_fn, tc["name"], tc["arguments"])
                for tc in tool_calls_received
            ]
        )
        for tc, tool_result in zip(tool_calls_received, dispatch_results):
            logger.info("Dispatching sub-tool: %s args=%s", tc["name"], tc["arguments"])
            logger.debug("Sub-tool %s result: %s", tc["name"], tool_result[:200])
            # Some providers (Databricks/LiteLLM) reject empty tool content with
            # BAD_REQUEST: Missing content in the tool message.
            # Always send at least a non-empty placeholder.
            tool_content = tool_result if tool_result and tool_result.strip() else "(empty)"
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_content,
            })

    return ToolResult(ok=True, result={"output": output_text})


def invoke_claude(
    prompt: str,
    sub_tools: list[dict],
    dispatch_fn,
    agent: Agent,
) -> ToolResult:
    """Synchronous wrapper around the async agentic loop."""
    return asyncio.run(_invoke_via_llm_connection(prompt, sub_tools, dispatch_fn, agent))


# ── Claude Code CLI subprocess ────────────────────────────────────────────────

def invoke_claude_cli(
    prompt: str,
    allowed_tools: list[str],
    args: dict[str, Any],
    agent: Agent | None = None,
) -> ToolResult:
    """Invoke Claude Code CLI as a one-shot subprocess."""
    import shutil
    from pathlib import Path

    try:
        claude_bin = shutil.which("claude")
        logger.debug("claude binary: %s", claude_bin or "NOT FOUND")
        if not claude_bin:
            return ToolResult(
                ok=False,
                error="Claude Code CLI not found on PATH. Run: npm install -g @anthropic-ai/claude-code",
            )

        # Use stdin for the prompt — avoids Windows CreateProcess arg length limits
        # and encoding issues when the prompt contains non-ASCII chars (e.g. ━)
        max_turns = args.get("max_turns", 100)
        cmd = [claude_bin, "-p", "-", "--output-format", "stream-json", "--verbose", "--max-turns", str(max_turns)]
        if allowed_tools:
            cmd += ["--allowedTools", ",".join(allowed_tools)]
        if args.get("session_id"):
            cmd += ["--session-id", args["session_id"]]

        cwd: str | None = None
        git_worktree_path = args.get("worktree_path")
        if git_worktree_path:
            wt = Path(git_worktree_path)
            if wt.is_dir():
                cwd = str(wt)
                logger.debug("claude CLI cwd: %s", cwd)
            else:
                logger.warning(
                    "worktree_path '%s' is not a directory — running in default cwd",
                    git_worktree_path,
                )

        cli_env = {**os.environ}
        # Disable Node.js TLS verification for self-signed / corporate proxy certificates
        cli_env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
        # Prevent git from blocking on credential prompts inside the subprocess
        cli_env["GIT_TERMINAL_PROMPT"] = "0"
        cli_env["GIT_ASKPASS"] = "echo"

        # Inject ANTHROPIC_BASE_URL for proxy connections (LiteLLM or any provider with base_url)
        conn = _get_llm_connection(agent) if agent is not None else None
        if not cli_env.get("ANTHROPIC_BASE_URL"):
            base_url = getattr(conn, "base_url", None) if conn else None
            if base_url:
                cli_env["ANTHROPIC_BASE_URL"] = base_url
                logger.debug("Injected ANTHROPIC_BASE_URL=%s for CLI subprocess", base_url)

        if not cli_env.get("ANTHROPIC_API_KEY"):
            cli_key = os.environ.get("CLAUDE_CLI_API_KEY", "")
            if cli_key:
                cli_env["ANTHROPIC_API_KEY"] = cli_key
                logger.debug("Injected ANTHROPIC_API_KEY from CLAUDE_CLI_API_KEY env var")
            elif conn is not None and getattr(conn, "api_key_enc", None):
                try:
                    from app.services.encryption import decrypt_field

                    api_key = decrypt_field(conn.api_key_enc)
                    if api_key:
                        cli_env["ANTHROPIC_API_KEY"] = api_key
                        logger.debug(
                            "Injected ANTHROPIC_API_KEY from agent LLM connection (provider=%s)",
                            getattr(conn, "provider", "unknown"),
                        )
                except Exception as key_exc:
                    logger.warning("Could not read LLM connection api_key: %s", key_exc)
            elif cli_env.get("ANTHROPIC_BASE_URL"):
                # Proxy doesn't require a real key — use a placeholder so the CLI doesn't abort
                cli_env["ANTHROPIC_API_KEY"] = "dummy"
                logger.debug("Using dummy ANTHROPIC_API_KEY for proxy connection")

        # Ensure git bash is available on Windows (required by Claude Code CLI)
        if not cli_env.get("CLAUDE_CODE_GIT_BASH_PATH"):
            import shutil
            git_bash = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
            common_paths = [
                r"C:\Users\{}\AppData\Local\Programs\Git\bin\bash.exe".format(os.environ.get("USERNAME", "")),
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
            ]
            for candidate in common_paths:
                if os.path.exists(candidate):
                    git_bash = candidate
                    break
            if git_bash:
                cli_env["CLAUDE_CODE_GIT_BASH_PATH"] = git_bash
                logger.debug("Injected CLAUDE_CODE_GIT_BASH_PATH=%s", git_bash)

        if cli_env.get("ANTHROPIC_API_KEY"):
            logger.debug("ANTHROPIC_API_KEY is set for CLI subprocess")
        else:
            logger.warning(
                "ANTHROPIC_API_KEY is NOT set for claude CLI subprocess — it will fail. "
                "Fix: set CLAUDE_CLI_API_KEY=... in your .env file."
            )

        logger.info("Invoking Claude CLI — cwd=%s cmd=%s", cwd, " ".join(cmd[:4]))
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        with subprocess.Popen(
            cmd,
            cwd=cwd,
            env=cli_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        ) as proc:
            import threading

            proc.stdin.write(prompt)
            proc.stdin.close()

            def _stream_stderr():
                for line in proc.stderr:
                    line = line.rstrip()
                    if line:
                        logger.info("[claude stderr] %s", line)
                        stderr_lines.append(line)

            stderr_thread = threading.Thread(target=_stream_stderr, daemon=True)
            stderr_thread.start()

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                stdout_lines.append(line)
                try:
                    obj = json.loads(line)
                    event_type = obj.get("type", "")
                    if event_type == "assistant":
                        # Log tool use calls; skip pure text chunks (too noisy)
                        for block in obj.get("message", {}).get("content", []):
                            if block.get("type") == "tool_use":
                                logger.info("[claude] tool_use: %s %s", block.get("name"), block.get("input", {}))
                    elif event_type == "tool_result":
                        logger.info("[claude] tool_result for tool_use_id=%s", obj.get("tool_use_id", ""))
                    elif event_type == "result":
                        subtype = obj.get("subtype", "")
                        errors = obj.get("errors", [])
                        result_text = obj.get("result", "")
                        logger.info(
                            "[claude] result: subtype=%s turns=%s cost=$%.4f",
                            subtype, obj.get("num_turns"), obj.get("total_cost_usd", 0),
                        )
                        if result_text:
                            logger.info("[claude] result text: %s", result_text[:2000])
                        if errors:
                            for err in errors:
                                logger.warning("[claude] error: %s", str(err)[:300])
                    elif event_type not in ("system", "user"):
                        logger.info("[claude] %s", line)
                except json.JSONDecodeError:
                    logger.info("[claude] %s", line)

            stderr_thread.join(timeout=5)

        returncode = proc.returncode
        stdout_text = "\n".join(stdout_lines)
        stderr_text = "\n".join(stderr_lines)

        logger.info("claude CLI exited with returncode=%d", returncode)

        if returncode != 0:
            error_detail = stderr_text.strip() or stdout_text.strip() or f"claude exited {returncode}"
            return ToolResult(ok=False, error=error_detail)

        result_data: dict = {}
        for line in stdout_lines:
            try:
                obj = json.loads(line)
                if obj.get("type") == "result":
                    result_data = obj
                    break
            except json.JSONDecodeError:
                pass

        if not result_data:
            return ToolResult(
                ok=False,
                error=f"No result line in claude output: {stdout_text[:200]}",
            )

        return ToolResult(
            ok=True,
            result={"output": result_data.get("result", ""), "session_id": result_data.get("session_id")},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, error="Claude Code CLI timed out after 300 seconds")
    except Exception as exc:
        logger.exception("Claude Code CLI invocation failed")
        return ToolResult(ok=False, error=f"CLI error: {type(exc).__name__}: {exc}")


# ── Claude Agent SDK ──────────────────────────────────────────────────────────

async def invoke_claude_sdk(
    prompt: str,
    allowed_tools: list[str],
    args: dict[str, Any],
    mcp_server,
) -> ToolResult:
    """Invoke Claude via the Claude Agent SDK with an MCP server."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        options = ClaudeAgentOptions(
            mcp_servers={"compass-agent-tools": mcp_server},
            allowed_tools=allowed_tools,
            cwd=args.get("worktree_path"),
        )

        output_chunks: list[str] = []
        async with ClaudeSDKClient(options=options) as client:
            async for message in client.query(prompt):
                text = getattr(message, "text", None) or ""
                if text:
                    output_chunks.append(text)

        return ToolResult(ok=True, result={"output": "".join(output_chunks)})
    except Exception as exc:
        logger.exception("Claude Agent SDK invocation failed")
        return ToolResult(ok=False, error=str(exc))
