"""AppChatSession and AppChatMessage models for the Apps IDE chat feature."""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base


class AppChatRole(str, PyEnum):
    user = "user"
    assistant = "assistant"
    tool = "tool"


class AppChatSession(Base):
    __tablename__ = "app_chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    llm_connection_id = Column(Integer, nullable=True)  # FK to LLMConnection in account db
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "AppChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AppChatMessage.created_at",
    )


class AppChatMessage(Base):
    __tablename__ = "app_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("app_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # user | assistant | tool
    content = Column(Text, nullable=True)
    tool_name = Column(String(100), nullable=True)
    tool_args = Column(JSON, nullable=True)
    tool_result = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    session = relationship("AppChatSession", back_populates="messages")
