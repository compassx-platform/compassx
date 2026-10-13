"""Data models and schemas for the Agent Runtime Module."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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
