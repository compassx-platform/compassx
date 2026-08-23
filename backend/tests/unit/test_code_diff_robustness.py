"""Unit tests for Code Diff & Change Capture Robustness."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SystemBase
from app.models.agents import Agent, ChatSession
from app.agents.services.agent.change_capture_service import (
    _compute_diff_counts,
    _normalize_text,
    capture_change,
    accept_change,
    reject_change,
    get_changes_for_session,
    get_change_record,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"jobs": None, "ai": None, "auth": None, "catalog": None}},
        poolclass=StaticPool,
    )
    SystemBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    agent = Agent(name="DiffTestAgent")
    session.add(agent)
    session.commit()

    chat_session = ChatSession(agent_id=agent.id, title="Diff Session")
    session.add(chat_session)
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_diff_counts_crlf_normalization():
    before = "line 1\r\nline 2\r\nline 3"
    after = "line 1\nline 2 modified\nline 3\nline 4"

    additions, deletions = _compute_diff_counts(before, after)
    # line 2 replaced with line 2 modified (1 del, 1 add), plus line 4 added (1 add) -> 2 adds, 1 del
    assert additions == 2
    assert deletions == 1


def test_change_capture_and_accept_flow(db_session):
    chat_session = db_session.query(ChatSession).first()

    rec = capture_change(
        db=db_session,
        session_id=chat_session.id,
        full_name="main.analytics.user_summary",
        object_type="table",
        before="SELECT id, name FROM users;",
        after="SELECT id, name, created_at, status FROM users;",
        step_id=1,
        plan_id="plan-123",
    )

    assert rec is not None
    assert rec.status == "pending_review"
    assert rec.additions > 0
    assert rec.step_id == 1
    assert rec.plan_id == "plan-123"

    # Accept change
    res = accept_change(db_session, rec.change_id)
    assert res["ok"] is True
    assert res["status"] == "accepted"

    # Retrieve change detail
    detail = get_change_record(db_session, rec.change_id)
    assert detail is not None
    assert detail["status"] == "accepted"
    assert "status FROM users" in detail["after_content"]


def test_change_reject_flow(db_session):
    chat_session = db_session.query(ChatSession).first()

    rec = capture_change(
        db=db_session,
        session_id=chat_session.id,
        full_name="workspace.notebooks.etl_pipeline",
        object_type="notebook",
        before="import pandas as pd\ndf = pd.read_csv('data.csv')",
        after="import polars as pl\ndf = pl.read_csv('data.csv')",
    )

    res = reject_change(db_session, rec.change_id, session_id=chat_session.id)
    assert res["ok"] is True
    assert res["status"] == "rejected"
    assert res["revert_change_id"] is not None

    # Check all changes for session
    all_changes = get_changes_for_session(db_session, chat_session.id)
    assert len(all_changes) == 2  # original (rejected) + revert record (accepted)
    assert all_changes[0]["status"] == "rejected"
    assert all_changes[1]["status"] == "accepted"
