"""Unit tests for Nova file attachments (Upload, Storage, Extraction, Context Delivery, Fetch Tool, Promotion)."""

from __future__ import annotations

import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SystemBase
from app.models.agents import Agent, ChatSession, NovaAttachment, NovaAttachmentPreview
from app.nova.services.attachment_service import (
    upload_attachment,
    get_context_payload,
    fetch_attachment_content,
    promote_attachment,
    D9_MAX_FILE_SIZE_BYTES,
    D10_MAX_CONCURRENT_ATTACHMENTS,
)
from app.nova.services.tools.fetch_attachment_tool import FetchAttachmentTool


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SystemBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create dummy agent & chat session
    agent = Agent(name="TestAgent", prompt="Test")
    session.add(agent)
    session.commit()

    chat_session = ChatSession(agent_id=agent.id, title="Test Session")
    session.add(chat_session)
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_upload_small_inline_attachment(db_session):
    chat_session = db_session.query(ChatSession).first()
    content = b"Line 1: Hello Nova\nLine 2: Small file attachment\nLine 3: End"
    
    attachment = upload_attachment(
        session_id=chat_session.id,
        user_id="user123",
        file_bytes=content,
        filename="small.txt",
        mime_type="text/plain",
        db=db_session,
    )

    assert attachment.status == "ready"
    assert attachment.delivery_mode == "inline"
    assert attachment.extracted_token_count < 3000

    payload = get_context_payload(attachment.file_id, db_session)
    assert payload["type"] == "inline"
    assert "Line 1: Hello Nova" in payload["content"]


def test_upload_large_tool_fetch_attachment(db_session):
    chat_session = db_session.query(ChatSession).first()
    # Create content larger than 3000 tokens (12000 chars)
    lines = [f"Line {i}: This is long repeated text to exceed 3000 tokens threshold." for i in range(300)]
    content = "\n".join(lines).encode("utf-8")

    attachment = upload_attachment(
        session_id=chat_session.id,
        user_id="user123",
        file_bytes=content,
        filename="large.txt",
        mime_type="text/plain",
        db=db_session,
    )

    assert attachment.status == "ready"
    assert attachment.delivery_mode == "tool_fetch"
    assert attachment.extracted_token_count > 3000

    payload = get_context_payload(attachment.file_id, db_session)
    assert payload["type"] == "tool_fetch"
    assert "fetch_attachment" in payload["instruction"]
    assert "Line 0:" in payload["preview_text"]


def test_fetch_attachment_tool_execution(db_session):
    chat_session = db_session.query(ChatSession).first()
    lines = [f"Line {i}: Alpha Beta Gamma {i}" for i in range(150)]
    content = "\n".join(lines).encode("utf-8")

    attachment = upload_attachment(
        session_id=chat_session.id,
        user_id="user123",
        file_bytes=content,
        filename="searchable.txt",
        mime_type="text/plain",
        db=db_session,
    )

    # Test tool class execution
    tool = FetchAttachmentTool()
    res = tool.execute(
        args={"file_id": str(attachment.file_id), "query": "Gamma 42", "line_start": 1, "line_end": 100},
        agent=None,
        db=db_session,
    )

    assert res.ok is True
    assert "Alpha Beta Gamma 42" in res.result["content"]


def test_promote_attachment(db_session):
    chat_session = db_session.query(ChatSession).first()
    content = b"Promote me"

    attachment = upload_attachment(
        session_id=chat_session.id,
        user_id="user123",
        file_bytes=content,
        filename="promotable.txt",
        mime_type="text/plain",
        db=db_session,
    )

    res = promote_attachment(
        file_id=attachment.file_id,
        target_catalog_path="main.default.promotable_file",
        user_id="user123",
        db=db_session,
    )

    assert res["ok"] is True
    assert res["promoted_object_id"] is not None
    db_session.refresh(attachment)
    assert attachment.promoted_object_id is not None


def test_max_file_size_limit(db_session):
    chat_session = db_session.query(ChatSession).first()
    oversized_content = b"X" * (D9_MAX_FILE_SIZE_BYTES + 1)

    with pytest.raises(HTTPException) as exc_info:
        upload_attachment(
            session_id=chat_session.id,
            user_id="user123",
            file_bytes=oversized_content,
            filename="oversized.bin",
            mime_type="application/octet-stream",
            db=db_session,
        )
    assert exc_info.value.status_code == 400


def test_fetch_attachment_page_execution(db_session):
    chat_session = db_session.query(ChatSession).first()
    content = (
        "=== Page 1 of 2 ===\nPage 1 Header\nLine 1\nLine 2\n"
        "=== Page 2 of 2 ===\nPage 2 Header\nLine 3\nLine 4\n"
    ).encode("utf-8")

    attachment = upload_attachment(
        session_id=chat_session.id,
        user_id="user123",
        file_bytes=content,
        filename="multipage.txt",
        mime_type="text/plain",
        db=db_session,
    )

    tool = FetchAttachmentTool()
    res = tool.execute(
        args={"file_id": str(attachment.file_id), "page": 2},
        agent=None,
        db=db_session,
    )

    assert res.ok is True
    assert "Page 2 Header" in res.result["content"]
    assert "Page 1 Header" not in res.result["content"]

