"""Unit tests for the Token-Based Watermark Compaction System (Spec D1-D10, O1-O5)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.agents.models.agents import ChatMessage, ChatSession, LLMConnection, MessageRole
from app.agents.services.agent.compactor.session_compactor import (
    ConversationTurn,
    compact_session_history,
    group_messages_into_turns,
    partition_turns_for_compaction,
    preflight_watermark_check,
)
from app.agents.services.agent.compactor.summary_schema import (
    STRUCTURED_SUMMARY_SCHEMA,
    build_compaction_user_prompt,
)
from app.agents.services.agent.compactor.token_estimator import (
    estimate_messages_tokens,
    estimate_text_tokens,
    resolve_model_context_window,
)


# ── Fixtures & Helpers ────────────────────────────────────────────────────────

def _make_mock_conn(model_name="gpt-4o", config=None):
    conn = MagicMock(spec=LLMConnection)
    conn.id = 1
    conn.model_name = model_name
    conn.config = config or {}
    conn.provider = "openai"
    return conn


def _make_sample_chat_messages(num_turns=6):
    messages = []
    msg_id = 1
    for t in range(1, num_turns + 1):
        # 1. User message
        messages.append(
            ChatMessage(
                id=msg_id,
                session_id=100,
                role=MessageRole.user,
                content=f"User request for turn {t}",
            )
        )
        msg_id += 1

        # 2. Tool message
        messages.append(
            ChatMessage(
                id=msg_id,
                session_id=100,
                role=MessageRole.tool,
                tool_name="sql_query",
                tool_result={
                    "args": {"query": f"SELECT * FROM sales_q{t}"},
                    "result": [{"quarter": f"Q{t}", "revenue": t * 1000}],
                    "ok": True,
                },
            )
        )
        msg_id += 1

        # 3. Assistant response
        messages.append(
            ChatMessage(
                id=msg_id,
                session_id=100,
                role=MessageRole.assistant,
                content=f"Assistant response for turn {t}",
            )
        )
        msg_id += 1

    return messages


# ── 1. Token Estimator & Context Window Resolution Tests ─────────────────────

def test_resolve_model_context_window():
    # Model catalog lookup
    assert resolve_model_context_window(_make_mock_conn("gpt-4o")) == 128_000
    assert resolve_model_context_window(_make_mock_conn("claude-3-5-sonnet-20241022")) == 200_000
    assert resolve_model_context_window(_make_mock_conn("gemini-1.5-pro")) == 1_000_000
    assert resolve_model_context_window(_make_mock_conn("deepseek-chat")) == 64_000
    assert resolve_model_context_window(_make_mock_conn("llama-3.3-70b-versatile")) == 128_000

    # Custom override via config
    assert resolve_model_context_window(_make_mock_conn("custom-model", config={"context_window": 50000})) == 50000

    # Default fallback
    assert resolve_model_context_window(_make_mock_conn("unknown-custom-model")) == 32_000
    assert resolve_model_context_window(None) == 32_000


def test_estimate_tokens():
    text = "Hello world! This is a test sentence."
    tokens = estimate_text_tokens(text)
    assert tokens > 0
    assert tokens == (len(text) + 3) // 4

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "How are you?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "test_tool", "arguments": '{"x": 1}'},
            }],
        },
        {"role": "tool", "name": "test_tool", "content": '{"status": "ok"}'},
    ]
    msg_tokens = estimate_messages_tokens(messages)
    assert msg_tokens > 20


# ── 2. Turn Grouping and Partitioning Tests ───────────────────────────────────

def test_group_messages_into_turns():
    raw_msgs = _make_sample_chat_messages(num_turns=4)
    turns = group_messages_into_turns(raw_msgs)

    assert len(turns) == 4
    for i, t in enumerate(turns, 1):
        assert t.turn_index == i
        assert t.user_message == f"User request for turn {i}"
        assert len(t.tool_calls) == 1
        assert t.tool_calls[0]["name"] == "sql_query"
        assert t.assistant_message == f"Assistant response for turn {i}"


def test_partition_turns_k3():
    raw_msgs = _make_sample_chat_messages(num_turns=7)
    turns = group_messages_into_turns(raw_msgs)

    turns_to_compact, turns_to_keep = partition_turns_for_compaction(turns, keep_last_k=3)

    assert len(turns_to_compact) == 4  # turns 1, 2, 3, 4
    assert len(turns_to_keep) == 3     # turns 5, 6, 7

    assert turns_to_compact[0].turn_index == 1
    assert turns_to_compact[-1].turn_index == 4
    assert turns_to_keep[0].turn_index == 5
    assert turns_to_keep[-1].turn_index == 7


def test_partition_turns_few_turns():
    raw_msgs = _make_sample_chat_messages(num_turns=2)
    turns = group_messages_into_turns(raw_msgs)

    turns_to_compact, turns_to_keep = partition_turns_for_compaction(turns, keep_last_k=3)
    assert len(turns_to_compact) == 0
    assert len(turns_to_keep) == 2


# ── 3. Prompt Builder & Schema Tests ──────────────────────────────────────────

def test_build_compaction_user_prompt():
    raw_msgs = _make_sample_chat_messages(num_turns=2)
    turns = group_messages_into_turns(raw_msgs)

    prompt_without_prev = build_compaction_user_prompt(
        existing_summary=None,
        turns_to_compact=[t.to_summary_dict() for t in turns],
    )
    assert "### RAW CONVERSATION TURNS TO FOLD AND COMPACT:" in prompt_without_prev
    assert "Turn 1" in prompt_without_prev
    assert "Turn 2" in prompt_without_prev
    assert "EXISTING SUMMARY" not in prompt_without_prev

    prompt_with_prev = build_compaction_user_prompt(
        existing_summary="Previous summary content here",
        turns_to_compact=[t.to_summary_dict() for t in turns],
    )
    assert "### EXISTING SUMMARY FROM PREVIOUS COMPACTION CYCLE:" in prompt_with_prev
    assert "Previous summary content here" in prompt_with_prev


# ── 4. Pre-Flight Watermark & Compaction Execution Tests ──────────────────────

@pytest.mark.asyncio
async def test_preflight_watermark_check_below_threshold():
    db = MagicMock(spec=Session)
    raw_msgs = _make_sample_chat_messages(num_turns=3)

    mock_query = MagicMock()
    mock_query.filter.return_value.order_by.return_value.all.return_value = raw_msgs
    db.query.return_value = mock_query

    session = ChatSession(id=100, title="Test", summary=None)
    conn = _make_mock_conn("gpt-4o")

    summary, retained_turns, did_compact = await preflight_watermark_check(
        session=session,
        db=db,
        conn=conn,
        system_prompt="System prompt",
        prefetched_messages=[],
        current_user_content="Next question",
        keep_last_k=3,
        high_watermark_ratio=0.85,
    )

    assert did_compact is False
    assert summary is None
    assert len(retained_turns) == 3


@pytest.mark.asyncio
async def test_preflight_watermark_check_triggers_compaction():
    db = MagicMock(spec=Session)
    raw_msgs = _make_sample_chat_messages(num_turns=6)

    mock_query = MagicMock()
    mock_query.filter.return_value.order_by.return_value.all.return_value = raw_msgs
    db.query.return_value = mock_query

    session = ChatSession(id=100, title="Test", summary=None)
    # Use low context window to trigger high watermark threshold
    conn = _make_mock_conn("custom", config={"context_window": 100})

    mock_summary_output = (
        "## Conversation Context & Progress Summary\n\n"
        "### 1. Primary User Goal / Intent\n- Process sales data\n\n"
        "### 2. Catalog Objects Touched\n- main.default.sales\n\n"
        "### 3. Queries Run & Key Findings\n- Total Q1-Q3 sales calculated"
    )

    async def _mock_stream(*args, **kwargs):
        yield {"type": "text", "delta": mock_summary_output}

    with patch("app.agents.services.llm_client.chat_stream", side_effect=_mock_stream):
        summary, retained_turns, did_compact = await preflight_watermark_check(
            session=session,
            db=db,
            conn=conn,
            system_prompt="System prompt",
            prefetched_messages=[],
            current_user_content="Next question",
            keep_last_k=3,
            high_watermark_ratio=0.85,
        )

    assert did_compact is True
    assert summary == mock_summary_output
    assert session.summary == mock_summary_output
    assert len(retained_turns) == 3
    assert db.commit.called


@pytest.mark.asyncio
async def test_manual_compact_force_trigger():
    db = MagicMock(spec=Session)
    raw_msgs = _make_sample_chat_messages(num_turns=5)

    mock_query = MagicMock()
    mock_query.filter.return_value.order_by.return_value.all.return_value = raw_msgs
    db.query.return_value = mock_query

    session = ChatSession(id=100, title="Test", summary=None)
    conn = _make_mock_conn("gpt-4o")

    mock_summary_output = "## Compacted Summary\n- Manual compaction executed."

    async def _mock_stream(*args, **kwargs):
        yield {"type": "text", "delta": mock_summary_output}

    with patch("app.agents.services.llm_client.chat_stream", side_effect=_mock_stream):
        summary, retained_turns, did_compact = await preflight_watermark_check(
            session=session,
            db=db,
            conn=conn,
            system_prompt="System prompt",
            prefetched_messages=[],
            current_user_content="/compact",
            keep_last_k=3,
            force_compact=True,
        )

    assert did_compact is True
    assert summary == mock_summary_output
    assert len(retained_turns) == 3


@pytest.mark.asyncio
async def test_summarizer_failure_fallback_non_blocking():
    db = MagicMock(spec=Session)
    raw_msgs = _make_sample_chat_messages(num_turns=6)

    mock_query = MagicMock()
    mock_query.filter.return_value.order_by.return_value.all.return_value = raw_msgs
    db.query.return_value = mock_query

    session = ChatSession(id=100, title="Test", summary="Existing summary")
    conn = _make_mock_conn("custom", config={"context_window": 100})

    async def _mock_failing_stream(*args, **kwargs):
        raise RuntimeError("LLM API Timeout")
        yield {}

    with patch("app.agents.services.llm_client.chat_stream", side_effect=_mock_failing_stream):
        # Should catch error gracefully and return without raising
        summary, retained_turns, did_compact = await preflight_watermark_check(
            session=session,
            db=db,
            conn=conn,
            system_prompt="System prompt",
            prefetched_messages=[],
            current_user_content="Next question",
            keep_last_k=3,
            high_watermark_ratio=0.85,
        )

    # Retains previous summary and returns last 3 turns
    assert summary == "Existing summary"
    assert len(retained_turns) == 3
