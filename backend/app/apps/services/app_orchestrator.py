"""App IDE chat orchestrator.

Mirrors agents/services/agent/orchestrator.py but scoped to an App/Branch
instead of an Agent. Uses the existing chat_stream LLM client and emits
the same SSE event format so the frontend can reuse the same renderer.

Event types emitted:
  {type: 'text', delta: str}
  {type: 'tool_start', tool_name: str, args: dict}
  {type: 'tool_end', tool_name: str, result: dict, ok: bool, error: str|None}
  {type: 'error', message: str}
  {type: 'done', usage: dict, session_id: int, message_id: int|None}
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.apps.models.app_chat import AppChatMessage, AppChatSession
from app.apps.services.app_tools import APP_TOOL_DEFINITIONS, execute_app_tool
from app.services.llm_client import chat_stream

logger = logging.getLogger(__name__)

_MAX_HISTORY = 40
_MAX_TOOL_ROUNDS = 15

APP_SYSTEM_PROMPT = """You are CompassX — an expert full-stack coding assistant embedded directly in the developer's IDE.

You have access to the following tools to help the user build their application:
- read_file: Read any file in the workspace
- write_file: Create or update files with new code
- list_files: Explore the directory structure
- delete_file: Remove files
- rename_file: Rename or move files

Guidelines:
- Always read relevant files before modifying them to understand the existing code
- Write complete, working code — never use placeholders like '...' or 'TODO'
- After writing a file, briefly explain what you changed and why
- When the user asks to build a feature, think step by step: plan → read context → write code → explain
- Prefer editing existing files over creating new ones unless adding new functionality
- Match the existing code style, imports, and patterns in the project
"""


def _resolve_llm_connection(llm_connection_id: int | None):
    """Resolve LLM connection from account DB, falling back to default."""
    from app.database import AccountSessionLocal
    from app.agents.models.agents import LLMConnection

    if AccountSessionLocal is None:
        return None

    acc_db = AccountSessionLocal()
    try:
        if llm_connection_id is not None:
            conn = (
                acc_db.query(LLMConnection)
                .filter(LLMConnection.id == llm_connection_id)
                .first()
            )
            if conn:
                acc_db.expunge(conn)
                return conn

        # Fallback: use is_fallback or first available
        conn = (
            acc_db.query(LLMConnection)
            .filter(LLMConnection.is_fallback.is_(True))
            .first()
        )
        if not conn:
            conn = (
                acc_db.query(LLMConnection)
                .order_by(LLMConnection.id.asc())
                .first()
            )
        if conn:
            acc_db.expunge(conn)
        return conn
    finally:
        acc_db.close()


async def app_orchestrate_stream(
    session_id: int,
    user_content: str,
    app_id: str,
    branch_id: str,
    db: Session,
    llm_connection_id: int | None = None,
) -> AsyncIterator[dict]:
    """Main app chat turn loop. Yields SSE-compatible event dicts."""
    # Load session
    session = db.query(AppChatSession).filter(AppChatSession.id == session_id).first()
    if not session:
        yield {"type": "error", "message": "Session not found"}
        return

    # Resolve LLM connection
    effective_conn_id = llm_connection_id or session.llm_connection_id
    llm_connection = _resolve_llm_connection(effective_conn_id)
    if not llm_connection:
        yield {
            "type": "error",
            "message": "No LLM connection configured. Add one in Settings > LLM Connections.",
        }
        return

    # Load message history (sliding window)
    history = (
        db.query(AppChatMessage)
        .filter(AppChatMessage.session_id == session_id)
        .order_by(AppChatMessage.created_at.desc())
        .limit(_MAX_HISTORY)
        .all()
    )
    history.reverse()

    messages: list[dict] = []
    for row in history:
        if row.role == "tool":
            continue
        messages.append({"role": row.role, "content": row.content or ""})

    # Persist user message
    user_msg = AppChatMessage(
        session_id=session_id,
        role="user",
        content=user_content,
    )
    db.add(user_msg)
    db.commit()
    messages.append({"role": "user", "content": user_content})

    # Update session LLM connection if provided by caller
    if llm_connection_id and session.llm_connection_id != llm_connection_id:
        session.llm_connection_id = llm_connection_id
        db.commit()

    # LLM agentic loop
    full_response_text = ""
    total_usage: dict = {}

    for _turn in range(_MAX_TOOL_ROUNDS):
        tool_calls_received: list[dict] = []

        try:
            async for event in chat_stream(
                conn=llm_connection,
                messages=messages,
                tools=APP_TOOL_DEFINITIONS,
                system_prompt=APP_SYSTEM_PROMPT,
                agent_id=None,  # not agent-scoped — skip budget check & llm call log
                session_id=session_id,
            ):
                match event["type"]:
                    case "text":
                        full_response_text += event["delta"]
                        yield {"type": "text", "delta": event["delta"]}
                    case "tool_use":
                        tool_calls_received.extend(event["tool_calls"])
                    case "done":
                        total_usage = event.get("usage", {})
        except Exception as exc:
            logger.exception(
                "LLM call failed in app chat session %s turn %d", session_id, _turn
            )
            yield {"type": "error", "message": str(exc)}
            return

        # No tool calls — LLM finished naturally
        if not tool_calls_received:
            break

        # Append assistant's tool-calling turn to message history
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls_received
                ],
            }
        )

        # Execute each tool and feed results back
        for tc in tool_calls_received:
            yield {"type": "tool_start", "tool_name": tc["name"], "args": tc["arguments"]}

            result = await execute_app_tool(
                tool_name=tc["name"],
                arguments=tc["arguments"],
                app_id=app_id,
                branch_id=branch_id,
                db=db,
            )

            ok = result["ok"]
            result_payload = result.get("result", {})
            error_payload = result.get("error")

            yield {
                "type": "tool_end",
                "tool_name": tc["name"],
                "args": tc["arguments"],
                "result": result_payload,
                "ok": ok,
                "error": error_payload,
            }

            # Persist tool log row
            tool_msg = AppChatMessage(
                session_id=session_id,
                role="tool",
                tool_name=tc["name"],
                tool_args=tc["arguments"],
                tool_result={"result": result_payload, "error": error_payload, "ok": ok},
            )
            db.add(tool_msg)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(
                        result_payload if ok else {"error": error_payload}
                    ),
                }
            )

        db.commit()

    # Persist final assistant message
    assistant_msg_id: int | None = None
    if full_response_text:
        asst_msg = AppChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_response_text,
        )
        db.add(asst_msg)
        if not session.title:
            session.title = user_content[:80]
        db.commit()
        db.refresh(asst_msg)
        assistant_msg_id = asst_msg.id

    yield {
        "type": "done",
        "usage": total_usage,
        "session_id": session_id,
        "message_id": assistant_msg_id,
    }
