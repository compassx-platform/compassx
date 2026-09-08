"""Unit tests for Agent Document Image Uploads and Orchestrator Context Integration."""

from __future__ import annotations

import io
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SystemBase
from app.models.agents import Agent, ChatSession, RagDocument, DocumentStatus
from app.agents.schemas.agent_manifest import AgentManifest, DocumentUploadCapability
from app.agents.services.document_processor import parse_document
from app.agents.services.agent.context_builder import build_agent_system_prompt


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"jobs": None, "ai": None, "auth": None, "catalog": None, "compute": None, "storage": None, "governance": None, "am": None, "workspace": None}},
        poolclass=StaticPool,
    )
    SystemBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    agent = Agent(name="TestVisionAgent", prompt="You are a data assistant.")
    session.add(agent)
    session.commit()

    chat_session = ChatSession(agent_id=agent.id, title="Test Image Session")
    session.add(chat_session)
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_agent_manifest_defaults_include_images():
    cap = DocumentUploadCapability()
    assert cap.enabled is True
    for ext in ["png", "jpg", "jpeg", "webp", "gif", "svg"]:
        assert ext in cap.accepted_types


def test_parse_document_images():
    fake_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    result = parse_document(fake_png_bytes, "image/png", "architecture_diagram.png")
    assert "[Image Document: architecture_diagram.png (image/png)" in result
    assert f"Size: {len(fake_png_bytes)} bytes" in result

    fake_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF..."
    result_jpg = parse_document(fake_jpeg_bytes, "image/jpeg", "chart.jpg")
    assert "[Image Document: chart.jpg (image/jpeg)" in result_jpg


def test_orchestrator_image_attachment_context(db_session):
    chat_session = db_session.query(ChatSession).first()
    
    # Add a PDF document
    pdf_doc = RagDocument(
        agent_id=chat_session.agent_id,
        session_id=chat_session.id,
        filename="report.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.ready,
        extracted_preview="[PDF Document: report.pdf | Total Pages: 2]",
    )
    # Add an Image document
    img_doc = RagDocument(
        agent_id=chat_session.agent_id,
        session_id=chat_session.id,
        filename="pipeline_flow.png",
        mime_type="image/png",
        size_bytes=2048,
        status=DocumentStatus.ready,
        extracted_preview="[Image Document: pipeline_flow.png (image/png) | Size: 2048 bytes]",
    )
    db_session.add_all([pdf_doc, img_doc])
    db_session.commit()

    agent = db_session.query(Agent).first()
    res = build_agent_system_prompt(db_session, agent, session_id=chat_session.id)

    assert "## Attached Session Files" in res.system_prompt
    assert "### Attached Image: pipeline_flow.png" in res.system_prompt
    assert "### Attached Document: report.pdf" in res.system_prompt
    assert res.has_attachment_tool_fetch is True


def test_convert_messages_to_anthropic_multimodal():
    from app.agents.services.llm_client import _convert_messages_to_anthropic
    
    b64_sample = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this diagram?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64_sample}"}
                }
            ]
        }
    ]

    converted = _convert_messages_to_anthropic(messages)
    assert len(converted) == 1
    assert converted[0]["role"] == "user"
    blocks = converted[0]["content"]
    assert isinstance(blocks, list)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "What is in this diagram?"
    assert blocks[1]["type"] == "image"
    assert blocks[1]["source"]["type"] == "base64"
    assert blocks[1]["source"]["media_type"] == "image/png"
    assert blocks[1]["source"]["data"] == b64_sample


def test_build_gemini_multimodal_content():
    from unittest.mock import MagicMock
    from app.agents.services.llm_client import _build_gemini_text_content

    types_mock = MagicMock()
    types_mock.Part.from_text = lambda text: {"text": text}
    types_mock.Part.from_bytes = lambda data, mime_type: {"data": data, "mime_type": mime_type}
    types_mock.Content = lambda role, parts: {"role": role, "parts": parts}

    b64_sample = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_sample}"}
            }
        ]
    }

    content = _build_gemini_text_content(msg, types_mock)
    assert content is not None
    assert content["role"] == "user"
    parts = content["parts"]
    assert len(parts) == 2
    assert parts[0]["text"] == "Describe this image"
    assert parts[1]["mime_type"] == "image/png"
    assert isinstance(parts[1]["data"], bytes)

