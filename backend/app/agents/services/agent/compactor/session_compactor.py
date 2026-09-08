"""Session Compactor Engine for Agent Watermark Compaction (Spec D1, D3, D5, D6, D8, D10)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.models.agents import ChatMessage, ChatSession, LLMConnection, MessageRole
from app.agents.services.agent.compactor.summary_schema import (
    SUMMARY_SYSTEM_PROMPT,
    build_compaction_user_prompt,
)
from app.agents.services.agent.compactor.token_estimator import (
    DEFAULT_HIGH_WATERMARK_RATIO,
    DEFAULT_LOW_WATERMARK_K,
    estimate_messages_tokens,
    estimate_text_tokens,
    resolve_model_context_window,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConversationTurn:
    """Represents a single atomic dialogue turn consisting of user intent, tools, and assistant output."""

    turn_index: int
    user_message: str
    user_msg_id: int | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    assistant_message: str | None = None
    assistant_msg_id: int | None = None
    raw_messages: list[ChatMessage] = field(default_factory=list)

    def to_summary_dict(self) -> dict[str, Any]:
        """Format turn data for the summarizer prompt."""
        return {
            "turn_index": self.turn_index,
            "user_message": self.user_message,
            "tool_calls": self.tool_calls,
            "assistant_message": self.assistant_message,
        }

    def to_llm_messages(self) -> list[dict[str, Any]]:
        """Convert this turn into standard OpenAI-compatible messages for model consumption."""
        msgs: list[dict[str, Any]] = []

        # 1. User message
        if self.user_message:
            msgs.append({
                "role": "user",
                "content": self.user_message,
                "id": self.user_msg_id,
            })

        # 2. Tool calls and results
        if self.tool_calls:
            # Group tool calls for the assistant message
            tc_payloads = []
            tool_res_msgs = []
            for tc in self.tool_calls:
                call_id = tc.get("id") or f"call_{tc.get('name')}_{self.turn_index}"
                tc_payloads.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tc.get("name"),
                        "arguments": json.dumps(tc.get("args")) if isinstance(tc.get("args"), (dict, list)) else str(tc.get("args") or "{}"),
                    },
                })
                # Tool result message
                res = tc.get("result")
                err = tc.get("error")
                content_str = json.dumps(res if tc.get("ok", True) else {"error": err}) if isinstance(res, (dict, list)) else str(res or err or "")
                tool_res_msgs.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tc.get("name"),
                    "content": content_str,
                })

            msgs.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tc_payloads,
            })
            msgs.extend(tool_res_msgs)

        # 3. Final Assistant response text
        if self.assistant_message:
            msgs.append({
                "role": "assistant",
                "content": self.assistant_message,
                "id": self.assistant_msg_id,
            })

        return msgs


def group_messages_into_turns(messages: list[ChatMessage]) -> list[ConversationTurn]:
    """Group flat chronological ChatMessage rows into discrete ConversationTurn objects."""
    turns: list[ConversationTurn] = []
    current_turn: ConversationTurn | None = None
    turn_counter = 0

    for msg in messages:
        if msg.role == MessageRole.user:
            if current_turn is not None:
                turns.append(current_turn)
            turn_counter += 1
            current_turn = ConversationTurn(
                turn_index=turn_counter,
                user_message=msg.content or "",
                user_msg_id=msg.id,
                raw_messages=[msg],
            )
        elif msg.role == MessageRole.tool:
            if current_turn is None:
                turn_counter += 1
                current_turn = ConversationTurn(
                    turn_index=turn_counter,
                    user_message="",
                    raw_messages=[msg],
                )
            else:
                current_turn.raw_messages.append(msg)

            # Extract tool details
            tool_res_dict = msg.tool_result or {}
            current_turn.tool_calls.append({
                "id": f"call_{msg.id}",
                "name": msg.tool_name or "unknown_tool",
                "args": tool_res_dict.get("args"),
                "result": tool_res_dict.get("result"),
                "error": tool_res_dict.get("error"),
                "ok": tool_res_dict.get("ok", True),
                "change": tool_res_dict.get("change"),
            })
        elif msg.role == MessageRole.assistant:
            if current_turn is None:
                turn_counter += 1
                current_turn = ConversationTurn(
                    turn_index=turn_counter,
                    user_message="",
                    raw_messages=[msg],
                )
            else:
                current_turn.raw_messages.append(msg)

            if msg.content:
                if current_turn.assistant_message:
                    current_turn.assistant_message += f"\n\n{msg.content}"
                else:
                    current_turn.assistant_message = msg.content
                    current_turn.assistant_msg_id = msg.id

    if current_turn is not None:
        turns.append(current_turn)

    return turns


def partition_turns_for_compaction(
    turns: list[ConversationTurn],
    keep_last_k: int = DEFAULT_LOW_WATERMARK_K,
) -> tuple[list[ConversationTurn], list[ConversationTurn]]:
    """Partition turns into (turns_to_compact, turns_to_keep).

    Guarantees at least the last K complete turns are preserved in full raw detail.
    """
    if len(turns) <= keep_last_k:
        return ([], turns)
    return (turns[:-keep_last_k], turns[-keep_last_k:])


async def run_compaction_llm_call(
    conn: LLMConnection,
    existing_summary: str | None,
    turns_to_compact: list[ConversationTurn],
    agent_id: int | None = None,
    session_id: int | None = None,
    workspace_id: str | None = None,
) -> str:
    """Execute the structured summarizer LLM call to fold older turns into the summary."""
    from app.agents.services.llm_client import chat_stream

    user_prompt = build_compaction_user_prompt(
        existing_summary=existing_summary,
        turns_to_compact=[t.to_summary_dict() for t in turns_to_compact],
    )

    summarizer_messages = [{"role": "user", "content": user_prompt}]

    response_text = ""
    async for event in chat_stream(
        conn=conn,
        messages=summarizer_messages,
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        agent_id=agent_id,
        session_id=session_id,
        workspace_id=workspace_id,
    ):
        if event.get("type") == "text":
            response_text += event.get("delta", "")

    cleaned = response_text.strip()
    if not cleaned:
        raise ValueError("Summarizer returned an empty response")

    return cleaned


async def compact_session_history(
    session: ChatSession,
    db: Session,
    conn: LLMConnection,
    keep_last_k: int = DEFAULT_LOW_WATERMARK_K,
    agent_id: int | None = None,
    workspace_id: str | None = None,
) -> tuple[str | None, list[ConversationTurn]]:
    """Compact the session's older turns into ChatSession.summary and return the retained raw turns."""
    # Load all messages for the session in chronological order
    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    turns = group_messages_into_turns(all_messages)
    turns_to_compact, turns_to_keep = partition_turns_for_compaction(turns, keep_last_k=keep_last_k)

    if not turns_to_compact:
        logger.info("Session %s has %d turns (<= K=%d); skipping compaction", session.id, len(turns), keep_last_k)
        return (session.summary, turns)

    logger.info(
        "Compacting session %s: folding %d older turns into summary, retaining last %d raw turns",
        session.id,
        len(turns_to_compact),
        len(turns_to_keep),
    )

    try:
        new_summary = await run_compaction_llm_call(
            conn=conn,
            existing_summary=session.summary,
            turns_to_compact=turns_to_compact,
            agent_id=agent_id,
            session_id=session.id,
            workspace_id=workspace_id,
        )

        # Persist the single folded summary to ChatSession (D6, D10)
        session.summary = new_summary
        session.summary_updated_at = _utcnow()
        db.commit()
        db.refresh(session)

        logger.info("Session %s summary updated successfully (%d chars)", session.id, len(new_summary))
        return (new_summary, turns_to_keep)

    except Exception as exc:
        logger.exception("Summarization call failed for session %s: %s", session.id, exc)
        # Fallback per O5: do not block the turn; return current summary and keep turns
        return (session.summary, turns_to_keep)


async def preflight_watermark_check(
    session: ChatSession,
    db: Session,
    conn: LLMConnection,
    system_prompt: str,
    prefetched_messages: list[dict[str, Any]],
    current_user_content: str,
    keep_last_k: int = DEFAULT_LOW_WATERMARK_K,
    high_watermark_ratio: float = DEFAULT_HIGH_WATERMARK_RATIO,
    force_compact: bool = False,
    agent_id: int | None = None,
    workspace_id: str | None = None,
) -> tuple[str | None, list[ConversationTurn], bool]:
    """Pre-flight check before assembling the LLM context (D8).

    Calculates total candidate context tokens. If >= high watermark (or forced via /compact),
    triggers one-shot compaction.

    Returns:
        (active_summary, retained_turns, did_compact)
    """
    # 1. Load existing session messages
    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    turns = group_messages_into_turns(all_messages)

    # 2. Check manual force trigger (e.g. /compact)
    if force_compact:
        logger.info("Manual compaction triggered for session %s", session.id)
        summary, retained_turns = await compact_session_history(
            session=session,
            db=db,
            conn=conn,
            keep_last_k=keep_last_k,
            agent_id=agent_id,
            workspace_id=workspace_id,
        )
        return (summary, retained_turns, True)

    # 3. Assemble candidate prompt payload to compute exact token count
    candidate_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if session.summary:
        candidate_messages.append({
            "role": "system",
            "content": f"## PREVIOUS CONVERSATION CONTEXT & PROGRESS SUMMARY:\n{session.summary}",
        })

    for t in turns:
        candidate_messages.extend(t.to_llm_messages())

    candidate_messages.extend(prefetched_messages)
    candidate_messages.append({"role": "user", "content": current_user_content})

    total_tokens = estimate_messages_tokens(candidate_messages)
    context_window = resolve_model_context_window(conn)
    high_watermark = int(context_window * high_watermark_ratio)

    logger.debug(
        "Pre-flight context check for session %s: estimated %d tokens / context window %d (watermark: %d, turns: %d)",
        session.id,
        total_tokens,
        context_window,
        high_watermark,
        len(turns),
    )

    # 4. If over high watermark and we have more than K turns, execute compaction (D1, D3)
    if total_tokens >= high_watermark and len(turns) > keep_last_k:
        logger.warning(
            "Session %s reached high watermark (%d >= %d tokens, %d turns). Triggering compaction.",
            session.id,
            total_tokens,
            high_watermark,
            len(turns),
        )
        summary, retained_turns = await compact_session_history(
            session=session,
            db=db,
            conn=conn,
            keep_last_k=keep_last_k,
            agent_id=agent_id,
            workspace_id=workspace_id,
        )
        return (summary, retained_turns, True)

    return (session.summary, turns, False)
