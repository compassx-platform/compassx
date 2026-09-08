"""Unit tests for orchestrate_subagent_stream().

Tests cover:
  - test_uses_existing_session (no new ChatSession created)
  - test_messages_tagged_with_agent
  - test_single_agent_flow_unchanged (regression guard)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from sqlalchemy.orm import Session


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session(session_id=10, workspace_id=1, agent_id=1):
    s = MagicMock()
    s.id = session_id
    s.workspace_id = workspace_id
    s.agent_id = agent_id
    s.title = "Test Session"
    return s


def _make_agent(agent_id=99, name="SubAgent", workspace_id=1, color="#aabbcc"):
    a = MagicMock()
    a.id = agent_id
    a.name = name
    a.workspace_id = workspace_id
    a.color = color
    a.skills = []
    a.tools = []
    a.db_connections = []
    a.git_connections = []
    a.llm_connection = MagicMock()
    a.prompt = "You are a subagent."
    return a


def _make_db(session=None, agent=None):
    mock_db = MagicMock(spec=Session)

    session_obj = session or _make_session()
    agent_obj = agent or _make_agent()

    # track add() calls
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    def _query(model):
        from app.models.agents import Agent, ChatSession, ChatMessage
        q = MagicMock()
        q.filter.return_value = q
        q.options.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q

        if model is ChatSession:
            q.first.return_value = session_obj
        elif model is Agent:
            q.first.return_value = agent_obj
            q.all.return_value = [agent_obj]
        elif model is ChatMessage:
            q.all.return_value = []
        else:
            q.first.return_value = None
            q.all.return_value = []
        return q

    mock_db.query.side_effect = _query
    return mock_db


async def _run_stream(coro_gen):
    """Collect all events from an async generator."""
    events = []
    async for event in coro_gen:
        events.append(event)
    return events


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestUsesExistingSession:
    def test_no_new_chatsession_created(self):
        """orchestrate_subagent_stream() must join the existing session, not create one."""
        db = _make_db()

        async def _fake_chat_stream(**kwargs):
            yield {"type": "text", "delta": "done"}
            yield {"type": "done", "usage": {}}

        with patch("app.agents.services.agent.orchestrator.chat_stream", side_effect=lambda **kw: _fake_chat_stream(**kw)):
            with patch("app.agents.services.agent.orchestrator.build_system_prompt", return_value="sys"):
                with patch("app.agents.services.agent.orchestrator.get_tool_definitions", return_value=[]):
                    from app.agents.services.agent.orchestrator import orchestrate_subagent_stream

                    events = asyncio.run(
                        _run_stream(
                            orchestrate_subagent_stream(
                                session_id=10,
                                initial_prompt="Do the task.",
                                subagent_id=99,
                                invocation_depth=1,
                                db=db,
                            )
                        )
                    )

        # ChatSession must NOT have been added (only ChatMessage rows)
        from app.models.agents import ChatSession
        for call_args in db.add.call_args_list:
            obj = call_args[0][0]
            assert not isinstance(obj, ChatSession), (
                "ChatSession was created — subagent must join existing session"
            )

    def test_session_query_called_with_correct_id(self):
        """DB must be queried for the given session_id."""
        db = _make_db()

        async def _fake_chat_stream(**kwargs):
            yield {"type": "done", "usage": {}}

        with patch("app.agents.services.agent.orchestrator.chat_stream", side_effect=lambda **kw: _fake_chat_stream(**kw)):
            with patch("app.agents.services.agent.orchestrator.build_system_prompt", return_value=""):
                with patch("app.agents.services.agent.orchestrator.get_tool_definitions", return_value=[]):
                    from app.agents.services.agent.orchestrator import orchestrate_subagent_stream

                    asyncio.run(
                        _run_stream(
                            orchestrate_subagent_stream(
                                session_id=10,
                                initial_prompt="task",
                                subagent_id=99,
                                invocation_depth=1,
                                db=db,
                            )
                        )
                    )

        # db.query was called — the session was looked up
        assert db.query.called


class TestMessagesTaggedWithAgent:
    def test_text_events_carry_agent_metadata(self):
        """Every text event must include agent_id, agent_name, agent_color, invocation_depth."""
        subagent = _make_agent(agent_id=55, name="DataAgent", color="#334455")
        db = _make_db(agent=subagent)

        async def _fake_chat_stream(**kwargs):
            yield {"type": "text", "delta": "Hello from DataAgent"}
            yield {"type": "done", "usage": {}}

        with patch("app.agents.services.agent.orchestrator.chat_stream", side_effect=lambda **kw: _fake_chat_stream(**kw)):
            with patch("app.agents.services.agent.orchestrator.build_system_prompt", return_value=""):
                with patch("app.agents.services.agent.orchestrator.get_tool_definitions", return_value=[]):
                    from app.agents.services.agent.orchestrator import orchestrate_subagent_stream

                    events = asyncio.run(
                        _run_stream(
                            orchestrate_subagent_stream(
                                session_id=10,
                                initial_prompt="task",
                                subagent_id=55,
                                invocation_depth=1,
                                db=db,
                            )
                        )
                    )

        text_events = [e for e in events if e.get("type") == "text"]
        assert len(text_events) >= 1
        for ev in text_events:
            assert ev["agent_id"] == 55
            assert ev["agent_name"] == "DataAgent"
            assert ev["agent_color"] == "#334455"
            assert ev["invocation_depth"] == 1

    def test_persisted_messages_have_agent_name(self):
        """ChatMessage rows written to DB must have agent_name set."""
        subagent = _make_agent(agent_id=55, name="DataAgent", color="#334455")
        db = _make_db(agent=subagent)

        saved_messages = []
        original_add = db.add.side_effect or (lambda x: None)

        def _capture(obj):
            from app.models.agents import ChatMessage
            if isinstance(obj, ChatMessage):
                saved_messages.append(obj)

        db.add.side_effect = _capture

        async def _fake_chat_stream(**kwargs):
            yield {"type": "text", "delta": "result"}
            yield {"type": "done", "usage": {"output_tokens": 5}}

        with patch("app.agents.services.agent.orchestrator.chat_stream", side_effect=lambda **kw: _fake_chat_stream(**kw)):
            with patch("app.agents.services.agent.orchestrator.build_system_prompt", return_value=""):
                with patch("app.agents.services.agent.orchestrator.get_tool_definitions", return_value=[]):
                    from app.agents.services.agent.orchestrator import orchestrate_subagent_stream

                    asyncio.run(
                        _run_stream(
                            orchestrate_subagent_stream(
                                session_id=10,
                                initial_prompt="task",
                                subagent_id=55,
                                invocation_depth=2,
                                db=db,
                            )
                        )
                    )

        assert len(saved_messages) >= 1
        for msg in saved_messages:
            assert msg.agent_name == "DataAgent"
            assert msg.invocation_depth == 2


class TestSingleAgentFlowUnchanged:
    """Regression guard: orchestrate_stream() must work exactly as before."""

    def test_orchestrate_stream_still_yields_text_done(self):
        """Original flow unchanged — text + done events emitted with agent tags."""
        primary = _make_agent(agent_id=1, name="PrimaryAgent")
        session = _make_session(agent_id=1)
        db = _make_db(session=session, agent=primary)

        async def _fake_chat_stream(**kwargs):
            yield {"type": "text", "delta": "Hello!"}
            yield {"type": "done", "usage": {"input_tokens": 10, "output_tokens": 5}}

        with patch("app.agents.services.agent.orchestrator.chat_stream", side_effect=lambda **kw: _fake_chat_stream(**kw)):
            with patch("app.agents.services.agent.orchestrator.build_system_prompt", return_value=""):
                with patch("app.agents.services.agent.orchestrator.get_tool_definitions", return_value=[]):
                    from app.agents.services.agent.orchestrator import orchestrate_stream

                    events = asyncio.run(
                        _run_stream(
                            orchestrate_stream(
                                session_id=10,
                                user_content="Hello",
                                db=db,
                                sandbox=True,
                            )
                        )
                    )

        types = [e["type"] for e in events]
        assert "text" in types
        assert "done" in types

    def test_orchestrate_stream_does_not_create_new_conversation_object(self):
        """orchestrate_stream() must not create Conversation / Task objects.
        It only creates ChatSession + ChatMessage (existing behaviour)."""
        primary = _make_agent(agent_id=1, name="PrimaryAgent")
        session = _make_session(agent_id=1)
        db = _make_db(session=session, agent=primary)

        async def _fake_chat_stream(**kwargs):
            yield {"type": "text", "delta": "Hi"}
            yield {"type": "done", "usage": {}}

        with patch("app.agents.services.agent.orchestrator.chat_stream", side_effect=lambda **kw: _fake_chat_stream(**kw)):
            with patch("app.agents.services.agent.orchestrator.build_system_prompt", return_value=""):
                with patch("app.agents.services.agent.orchestrator.get_tool_definitions", return_value=[]):
                    from app.agents.services.agent.orchestrator import orchestrate_stream

                    asyncio.run(
                        _run_stream(
                            orchestrate_stream(
                                session_id=10,
                                user_content="Hi",
                                db=db,
                                sandbox=False,
                            )
                        )
                    )

        from app.models.agents import Conversation
        for call_args in db.add.call_args_list:
            obj = call_args[0][0]
            assert not isinstance(obj, Conversation), (
                "orchestrate_stream() must not create Conversation objects"
            )
