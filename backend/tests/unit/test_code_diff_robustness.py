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


def test_physical_file_reversion_on_reject(tmp_path, db_session):
    chat_session = db_session.query(ChatSession).first()

    # Create a dummy file on disk
    test_file = tmp_path / "app_code.py"
    original_code = "def hello():\n    return 'original'\n"
    modified_code = "def hello():\n    return 'modified by agent'\n"
    test_file.write_text(modified_code, encoding="utf-8")

    rec = capture_change(
        db=db_session,
        session_id=chat_session.id,
        full_name=str(test_file),
        object_type="file",
        before=original_code,
        after=modified_code,
    )

    assert test_file.read_text(encoding="utf-8") == modified_code

    # Reject change -> must physically restore original content
    res = reject_change(db_session, rec.change_id, session_id=chat_session.id)
    assert res["ok"] is True
    assert res["status"] == "rejected"
    assert test_file.read_text(encoding="utf-8") == original_code


def test_bulk_review_changes_flow(db_session):
    from app.agents.services.agent.change_capture_service import bulk_review_changes

    chat_session = db_session.query(ChatSession).first()

    rec1 = capture_change(
        db=db_session,
        session_id=chat_session.id,
        full_name="file1.py",
        object_type="file",
        before="v1",
        after="v2",
    )
    rec2 = capture_change(
        db=db_session,
        session_id=chat_session.id,
        full_name="file2.py",
        object_type="file",
        before="a1",
        after="a2",
    )

    res = bulk_review_changes(db_session, chat_session.id, action="accept_all")
    assert res["ok"] is True
    assert res["count"] == 2

    # Verify both are accepted
    ch1 = get_change_record(db_session, rec1.change_id)
    ch2 = get_change_record(db_session, rec2.change_id)
    assert ch1["status"] == "accepted"
    assert ch2["status"] == "accepted"

