"""Tool dispatcher — routes a tool_call to the correct tool handler.

Called by the orchestrator after the LLM returns a tool_use block.
Returns a ToolResult that is appended to the message history as a
tool result.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.registry import TOOL_MAP

logger = logging.getLogger(__name__)


async def execute_tool(
    tool_key: str,
    arguments: dict[str, Any],
    agent: Agent,
    db: Session,
    extra_tools: dict[str, BaseTool] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch a tool call and return its output as a plain dict.

    Args:
        tool_key:    e.g. "sql_query", "python_code", "invoke_agent"
        arguments:   Parsed arguments from LLM tool_call
        agent:       Agent ORM row (with tools + db_connections loaded)
        db:          SQLAlchemy session
        extra_tools: Per-request tool instances (checked before global TOOL_MAP).
                     Used for stateful tools like InvokeAgentTool that need
                     runtime context (session_id, workspace_id, etc.).

    Returns:
        {"ok": bool, "result": dict, "error": str|None, "duration_ms": int}
    """
    start = time.monotonic()
    try:
        result = await _dispatch(tool_key, arguments, agent, db, extra_tools, runtime_context)
        result.duration_ms = int((time.monotonic() - start) * 1000)
        return result.to_dict()
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning("Tool %s failed: %s", tool_key, exc)
        return ToolResult(ok=False, error=str(exc), duration_ms=duration_ms).to_dict()


async def _dispatch(
    tool_key: str,
    args: dict[str, Any],
    agent: Agent,
    db: Session,
    extra_tools: dict[str, BaseTool] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> ToolResult:
    # Extra per-request tools take priority over the global registry
    tool = (extra_tools or {}).get(tool_key) or TOOL_MAP.get(tool_key)
    if tool is None:
        raise ValueError(f"Unknown tool: {tool_key}")

    if runtime_context and "context" not in args:
        args = {**args, "context": runtime_context}

    if tool.is_async:
        return await asyncio.to_thread(tool.execute, args, agent, db)
    return tool.execute(args, agent, db)

