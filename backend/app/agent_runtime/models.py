"""Data models and schemas for the Agent Runtime Module."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


from sqlalchemy import Column, DateTime, JSON, String
from sqlalchemy.dialects.postgresql import JSONB

from app.database import SystemBase


class CreateAgentSessionRequest(BaseModel):
    """Payload to create an agent runtime session."""
    title: Optional[str] = Field(default="Agent Session", description="User-friendly session title")
    agent_type: str = Field(default="antigravity", description="'antigravity', 'pi', or 'opencode'")
    sandbox_mode: str = Field(default="new", description="'new' or 'existing'")
    sandbox_id: Optional[str] = Field(default=None, description="Existing sandbox ID if sandbox_mode=='existing'")


class AgentChatMessage(BaseModel):
    """Single message in an agent runtime session."""
    id: str = Field(description="Message ID")
    role: str = Field(description="'user', 'assistant', or 'system'")
    content: str = Field(description="Message text / response content")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool_calls: Optional[List[Dict[str, Any]]] = None


class SendMessageRequest(BaseModel):
    """Payload to send a message to the agent."""
    content: str = Field(description="User prompt text")


class AgentRuntimeSession(BaseModel):
    """Agent runtime session model bound to an immutable sandbox."""
    id: str = Field(description="Session ID, e.g. ars_abc123")
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID")
    title: str = Field(description="Session title")
    agent_type: str = Field(description="'antigravity', 'pi', or 'opencode'")
    sandbox_id: str = Field(description="Bound compute sandbox ID (IMMUTABLE)")
    status: str = Field(default="active", description="'active', 'idle', 'stopped'")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: List[AgentChatMessage] = Field(default_factory=list)


class AgentRuntimeSessionDB(SystemBase):
    """SQLAlchemy model for agent runtime sessions in compassx_system database."""
    __tablename__ = "agent_runtime_sessions"

    id = Column(String(64), primary_key=True)
    workspace_id = Column(String(64), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="Agent Session")
    agent_type = Column(String(64), nullable=False, default="antigravity")
    sandbox_id = Column(String(128), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    messages = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)

    def to_pydantic(self) -> AgentRuntimeSession:
        raw_msgs = self.messages or []
        parsed_msgs = [AgentChatMessage(**m) if isinstance(m, dict) else m for m in raw_msgs]
        return AgentRuntimeSession(
            id=self.id,
            workspace_id=self.workspace_id,
            title=self.title,
            agent_type=self.agent_type,
            sandbox_id=self.sandbox_id,
            status=self.status,
            created_at=self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            updated_at=self.updated_at.isoformat() if self.updated_at else datetime.now(timezone.utc).isoformat(),
            messages=parsed_msgs,
        )

