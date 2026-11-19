"""Data models and schemas for the Agent Runtime Module."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.database import SystemBase


class CreateAgentSessionRequest(BaseModel):
    """Payload to create an agent runtime session."""
    title: Optional[str] = Field(default="Agent Session", description="User-friendly session title")
    agent_type: str = Field(default="nova", description="'nova', 'antigravity', 'pi', 'opencode', 'claude', 'codex', or 'cursor'")
    sandbox_mode: str = Field(default="new", description="'new' or 'existing'")
    sandbox_id: Optional[str] = Field(default=None, description="Existing sandbox ID if sandbox_mode=='existing'")
    project_id: Optional[str] = Field(default=None, description="Project this session belongs to")
    branch: Optional[str] = Field(default=None, description="Git branch to check out before the agent starts")
    llm_model: Optional[str] = Field(default=None, description="AI Gateway model name for Nova")


class GitInfoResponse(BaseModel):
    repo: bool = False
    branch: str = ""
    branches: List[str] = Field(default_factory=list)


class CreateProjectRequest(BaseModel):
    """Payload to create an agent runtime project."""
    name: str = Field(description="Project name")


class AgentChatMessage(BaseModel):
    """Single message in an agent runtime session."""
    id: str = Field(description="Message ID")
    role: str = Field(description="'user', 'assistant', or 'system'")
    content: str = Field(description="Message text / response content")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool_calls: Optional[List[Dict[str, Any]]] = None
    kind: Optional[str] = Field(default=None, description="'thinking', 'tool', 'reply', 'plan', 'debug', or 'error'")
    source_id: Optional[str] = Field(default=None, description="Stable id from the agent transcript")
    image: Optional[str] = Field(default=None, description="Data URL for a browser annotation screenshot")


class SendMessageRequest(BaseModel):
    """Payload to send a message to the agent."""
    content: str = Field(description="User prompt text")
    llm_model: Optional[str] = Field(default=None, description="AI Gateway model name for Nova")
    mode: Optional[str] = Field(default=None, description="Nova mode: agent, ask, plan, or debug")


class BrowserOpenRequest(BaseModel):
    url: str
    width: int = 800
    height: int = 600
    tab_id: str = "browser"


class BrowserInputRequest(BaseModel):
    tab_id: str = "browser"
    kind: str
    x: float = 0
    y: float = 0
    delta_y: float = 0
    key: str = ""
    text: str = ""


class BrowserPointRequest(BaseModel):
    tab_id: str = "browser"
    x: float
    y: float


class BrowserBox(BaseModel):
    left: float
    top: float
    width: float
    height: float


class BrowserTargetResponse(BaseModel):
    label: str
    detail: str
    box: BrowserBox


class BrowserNoteRequest(BaseModel):
    tab_id: str = "browser"
    instruction: str
    x: float
    y: float
    width: float
    height: float


class AgentCatalogItem(BaseModel):
    id: str
    label: str


class AgentOutputResponse(BaseModel):
    output: str = ""


class WorkspaceEntry(BaseModel):
    path: str
    type: str
    size: int = 0


class WorkspaceFilesResponse(BaseModel):
    root: str = "/workspace"
    entries: List[WorkspaceEntry] = Field(default_factory=list)


class FileContentResponse(BaseModel):
    path: str
    content: str = ""
    truncated: bool = False
    missing: bool = False


class WriteFileRequest(BaseModel):
    path: str
    content: str = ""


class WriteFileResponse(BaseModel):
    path: str
    bytes: int = 0


class ChangeEntry(BaseModel):
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    staged: bool = False
    unstaged: bool = True


class CommitEntry(BaseModel):
    hash: str
    subject: str = ""
    author: str = ""
    date: str = ""


class ChangesResponse(BaseModel):
    entries: List[ChangeEntry] = Field(default_factory=list)
    branch: str = ""
    commits: List[CommitEntry] = Field(default_factory=list)


class DiffResponse(BaseModel):
    path: str
    diff: str = ""


class AgentRuntimeSession(BaseModel):
    """Agent runtime session model bound to an immutable sandbox."""
    id: str = Field(description="Session ID, e.g. ars_abc123")
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID")
    title: str = Field(description="Session title")
    agent_type: str = Field(description="'nova', 'antigravity', 'pi', 'opencode', 'claude', 'codex', or 'cursor'")
    sandbox_id: str = Field(description="Bound compute sandbox ID (IMMUTABLE)")
    project_id: Optional[str] = Field(default=None, description="Owning project ID")
    llm_model: Optional[str] = Field(default=None, description="AI Gateway model selected for Nova")
    nova_chat_session_id: Optional[int] = Field(default=None, description="Bound Agents chat session for Nova")
    status: str = Field(default="active", description="'active', 'idle', 'stopped'")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: List[AgentChatMessage] = Field(default_factory=list)


class AgentRuntimeProject(BaseModel):
    """A named group of agent runtime sessions."""
    id: str
    workspace_id: Optional[str] = None
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentRuntimeProjectDB(SystemBase):
    """SQLAlchemy model for agent runtime projects."""
    __tablename__ = "agent_runtime_projects"

    id = Column(String(64), primary_key=True)
    workspace_id = Column(String(64), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_pydantic(self) -> AgentRuntimeProject:
        return AgentRuntimeProject(
            id=self.id,
            workspace_id=self.workspace_id,
            name=self.name,
            created_at=self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            updated_at=self.updated_at.isoformat() if self.updated_at else datetime.now(timezone.utc).isoformat(),
        )


class TaskEvent(BaseModel):
    """One recorded move of an agent runtime task."""
    at: str
    actor: str
    action: str
    from_stage: str = ""
    to_stage: str = ""
    note: str = ""


class CreateAgentTaskRequest(BaseModel):
    """Payload to file an agent runtime task. It starts in draft and does not run."""
    title: str
    brief: str = ""
    project_id: Optional[str] = None
    source_session_id: Optional[str] = None
    agent_type: str = "nova"
    llm_model: Optional[str] = None
    actor: str = Field(default="person", description="'person' or 'agent'")


class TaskNoteRequest(BaseModel):
    """A reason or review comment. Waiting and changes requested require one."""
    note: str = ""
    actor: str = Field(default="person", description="'person' or 'agent'")


class AgentRuntimeTask(BaseModel):
    """Work that waits in Agent Runtime until a person marks it ready."""
    id: str
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    title: str
    brief: str = ""
    stage: str = "draft"
    waiting_reason: str = ""
    start_error: str = ""
    source_session_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_type: str = "nova"
    llm_model: Optional[str] = None
    events: List[TaskEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentRuntimeTaskDB(SystemBase):
    """SQLAlchemy model for agent runtime tasks."""
    __tablename__ = "agent_runtime_tasks"

    id = Column(String(64), primary_key=True)
    workspace_id = Column(String(64), nullable=True, index=True)
    project_id = Column(String(64), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    brief = Column(Text, nullable=False, default="")
    stage = Column(String(32), nullable=False, default="draft", index=True)
    waiting_reason = Column(Text, nullable=False, default="")
    start_error = Column(Text, nullable=False, default="")
    source_session_id = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True, index=True)
    agent_type = Column(String(64), nullable=False, default="nova")
    llm_model = Column(String(255), nullable=True)
    events = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_pydantic(self) -> AgentRuntimeTask:
        raw_events = self.events or []
        events = [TaskEvent(**item) if isinstance(item, dict) else item for item in raw_events]
        return AgentRuntimeTask(
            id=self.id,
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            title=self.title,
            brief=self.brief or "",
            stage=self.stage,
            waiting_reason=self.waiting_reason or "",
            start_error=self.start_error or "",
            source_session_id=self.source_session_id,
            session_id=self.session_id,
            agent_type=self.agent_type,
            llm_model=self.llm_model,
            events=events,
            created_at=self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            updated_at=self.updated_at.isoformat() if self.updated_at else datetime.now(timezone.utc).isoformat(),
        )


class AgentRuntimeSessionDB(SystemBase):
    """SQLAlchemy model for agent runtime sessions in compassx_system database."""
    __tablename__ = "agent_runtime_sessions"

    id = Column(String(64), primary_key=True)
    workspace_id = Column(String(64), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="Agent Session")
    agent_type = Column(String(64), nullable=False, default="nova")
    sandbox_id = Column(String(128), nullable=False, index=True)
    project_id = Column(String(64), nullable=True, index=True)
    llm_model = Column(String(255), nullable=True)
    nova_chat_session_id = Column(Integer, nullable=True)
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
            project_id=self.project_id,
            llm_model=self.llm_model,
            nova_chat_session_id=self.nova_chat_session_id,
            status=self.status,
            created_at=self.created_at.isoformat() if self.created_at else datetime.now(timezone.utc).isoformat(),
            updated_at=self.updated_at.isoformat() if self.updated_at else datetime.now(timezone.utc).isoformat(),
            messages=parsed_msgs,
        )

