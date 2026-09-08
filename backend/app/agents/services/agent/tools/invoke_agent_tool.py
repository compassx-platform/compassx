"""invoke_agent tool — lets one agent hand off a subtask to another.

This tool is *stateful*: it is instantiated fresh per-request inside
``orchestrate_stream()`` / ``orchestrate_subagent_stream()`` with the
runtime context (session_id, etc.) baked in.

It is also registered in TOOL_REGISTRY as a zero-arg sentinel so
agents can enable it via their assigned tool set. The sentinel
instance raises RuntimeError if execute() is called directly
(the live instance is always used at call-time).

Architecture note
-----------------
``is_async = True`` means the tool dispatcher runs execute() in a thread via
``asyncio.to_thread``. But orchestrate_subagent_stream() is an async
generator that must be awaited. We bridge the sync-to-async gap by running
the coroutine on the already-running event loop from the background thread
using asyncio.run_coroutine_threadsafe().
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent, ChatMessage, MessageRole
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_MAX_HISTORY = 20
_MAX_DEPTH = 3


@dataclass
class SubagentResult:
    agent_id: int
    agent_name: str
    last_output: str
    message_count: int


class InvokeAgentTool(BaseTool):
    """Invoke another agent to handle a subtask.

    When assigned to an agent, that agent can delegate work to any other
    active agent. Both agents' messages appear in the same chat session so
    the user sees everything in real time.

    Instantiate with runtime context (session_id, etc.) for actual
    execution. The zero-arg sentinel form is only for tool listing.
    """

    key = "invoke_agent"
    name = "Invoke Agent"
    description = (
        "Invoke another agent to handle a subtask. "
        "The invoked agent runs in the same conversation so the user "
        "can see everything it does in real time. "
        "Use this when the task needs a specialist you are not. "
        "Do not use this for tasks you can handle yourself."
    )
    is_async = True
    input_schema = {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "The exact name of the agent to invoke.",
            },
            "task": {
                "type": "string",
                "description": (
                    "Clear, specific instruction for what the agent must do. "
                    "Include what format you want the result in."
                ),
            },
            "context": {
                "type": "string",
                "description": "Extra context beyond the conversation history.",
            },
            "wait_for_result": {
                "type": "boolean",
                "description": (
                    "True = wait for agent to finish before continuing (default). "
                    "False = run in parallel, continue immediately."
                ),
            },
        },
        "required": ["agent_name", "task"],
    }

    def __init__(
        self,
        *,
        session_id: int | None = None,
        invoking_agent_name: str = "",
        invocation_depth: int = 0,
        db: Session | None = None,
        _loop: asyncio.AbstractEventLoop | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        self._session_id = session_id
        self._invoking_agent_name = invoking_agent_name
        self._invocation_depth = invocation_depth
        self._db = db
        self._loop = _loop
        self._user_id = user_id
        self._workspace_id = workspace_id

    @property
    def _is_sentinel(self) -> bool:
        return self._session_id is None

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        if self._is_sentinel:
            raise RuntimeError(
                "InvokeAgentTool sentinel cannot be executed directly. "
                "A live instance with runtime context must be used."
            )

        _db = self._db or db

        if self._invocation_depth >= _MAX_DEPTH:
            return ToolResult(
                ok=False,
                error=(
                    f"Maximum invocation depth reached ({_MAX_DEPTH}). "
                    "Synthesise from what you already have."
                ),
            )

        target_name: str = args["agent_name"]
        task_text: str = args["task"]
        extra_context: str = args.get("context", "")
        wait_for_result: bool = args.get("wait_for_result", True)

        from app.models.agents import Agent as AgentModel

        active_agents = _db.query(AgentModel).filter(AgentModel.is_active.is_(True)).all()
        target_agent = next((a for a in active_agents if a.name.lower() == target_name.lower()), None)

        if target_agent is None:
            available = [row.name for row in _db.query(AgentModel.name).filter(AgentModel.is_active.is_(True)).all()]
            return ToolResult(
                ok=False,
                error=f"No agent named '{target_name}' found.",
                result={"available_agents": available},
            )

        if target_agent.status == "paused":
            return ToolResult(
                ok=False,
                error=f"Agent '{target_agent.name}' is paused due to budget exhaustion or admin action.",
            )

        history_rows = (
            _db.query(ChatMessage)
            .filter(ChatMessage.session_id == self._session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(_MAX_HISTORY)
            .all()
        )
        history_rows.reverse()
        history_lines = []
        for row in history_rows:
            label = row.agent_name or self._invoking_agent_name or "agent"
            role_label = row.role.value if row.role else "message"
            content = row.content or ""
            history_lines.append(f"[{label}] {role_label}: {content[:300]}")
        history = "\n".join(history_lines) or "(no prior messages)"

        initial_prompt = (
            f"You have been invoked by {self._invoking_agent_name} to handle a subtask.\n\n"
            f"CONVERSATION SO FAR:\n{history}\n\n"
            f"YOUR TASK:\n{task_text}\n\n"
            f"ADDITIONAL CONTEXT:\n{extra_context or 'None'}\n\n"
            "Complete your task and post your findings to the conversation. "
            "Be specific and concise — focus only on your assigned task."
        )

        system_msg = ChatMessage(
            session_id=self._session_id,
            role=MessageRole.tool,
            content=None,
            tool_name="invoke_agent",
            tool_result={
                "source": "system",
                "content": f"{self._invoking_agent_name or 'Agent'} invoked {target_agent.name}",
                "metadata": {
                    "invoked_by": self._invoking_agent_name,
                    "invoked_agent": target_agent.name,
                    "task": task_text[:120],
                },
            },
            agent_name=self._invoking_agent_name or None,
            invocation_depth=self._invocation_depth,
        )
        _db.add(system_msg)
        _db.commit()

        logger.info(
            "invoke_agent: %s -> %s (depth %d, session %s)",
            self._invoking_agent_name,
            target_agent.name,
            self._invocation_depth,
            self._session_id,
        )

        from app.agents.services.agent.orchestrator import orchestrate_subagent_stream

        async def _collect() -> SubagentResult:
            result = SubagentResult(
                agent_id=target_agent.id,
                agent_name=target_agent.name,
                last_output="",
                message_count=0,
            )
            async for event in orchestrate_subagent_stream(
                session_id=self._session_id,
                initial_prompt=initial_prompt,
                subagent_id=target_agent.id,
                invocation_depth=self._invocation_depth + 1,
                db=_db,
                user_id=self._user_id,
                workspace_id=self._workspace_id,
            ):
                if event.get("type") == "text":
                    result.last_output += event.get("delta", "")
                    result.message_count += 1
            return result

        loop = self._loop or asyncio.get_event_loop()
        if wait_for_result:
            future = asyncio.run_coroutine_threadsafe(_collect(), loop)
            try:
                subagent_result = future.result(timeout=300)
            except Exception as exc:
                logger.exception("invoke_agent: subagent %s failed: %s", target_agent.name, exc)
                return ToolResult(
                    ok=False,
                    error=f"Subagent '{target_agent.name}' raised an error: {exc}",
                )
            return ToolResult(
                ok=True,
                result={
                    "success": True,
                    "agent": target_agent.name,
                    "summary": subagent_result.last_output[-2000:],
                    "message": f"{target_agent.name} completed. Findings are in the conversation above.",
                },
            )

        asyncio.run_coroutine_threadsafe(_collect(), loop)
        return ToolResult(
            ok=True,
            result={
                "success": True,
                "agent": target_agent.name,
                "status": "running",
                "message": f"{target_agent.name} is running. Watch the conversation for its output.",
            },
        )
