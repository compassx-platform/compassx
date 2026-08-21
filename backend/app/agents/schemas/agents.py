"""Pydantic v2 schemas for the Agents module.

All response schemas mask encrypted fields (api_key_enc → api_key_masked).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.agents import LLMProvider, TriggerType, TaskStatus, MessageType

GIT_PROVIDERS = {"github", "azure_devops"}


# ── Workspaces ────────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    fallback_llm_connection_id: int | None = None


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    description: str | None
    fallback_llm_connection_id: int | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceMemberCreate(BaseModel):
    user_id: str
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"admin", "editor", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class WorkspaceMemberResponse(BaseModel):
    id: int
    user_id: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── LLM Connections ───────────────────────────────────────────────────────────

class LLMConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    provider: LLMProvider
    model_name: str
    api_key: str | None = None          # plain text; encrypted before saving
    base_url: str | None = None
    timeout_s: int = 120
    max_tokens: int = 4096
    config: dict[str, Any] = {}
    is_fallback: bool = False
    use_for_embedding: bool = False
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None
    cost_currency: str | None = "USD"


class LLMConnectionUpdate(BaseModel):
    name: str | None = None
    model_name: str | None = None
    api_key: str | None = None          # plain text; re-encrypt if provided
    base_url: str | None = None
    timeout_s: int | None = None
    max_tokens: int | None = None
    config: dict[str, Any] | None = None
    is_fallback: bool | None = None
    use_for_embedding: bool | None = None
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None
    cost_currency: str | None = None


class LLMConnectionResponse(BaseModel):
    id: int
    name: str
    provider: LLMProvider
    model_name: str
    api_key_masked: str | None = None   # "***...abcd"
    base_url: str | None
    timeout_s: int
    max_tokens: int
    config: dict[str, Any]
    is_fallback: bool
    use_for_embedding: bool
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None
    cost_currency: str | None = None
    cost_configured_at: datetime | None = None
    cost_configured_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PingResponse(BaseModel):
    success: bool
    message: str


# ── DB Connections ────────────────────────────────────────────────────────────

class DBConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    db_type: str
    host: str | None = None
    port: int | None = None
    db_name: str | None = None
    username: str | None = None         # plain text; encrypted before saving
    password: str | None = None         # plain text; encrypted before saving
    ssl_config: dict[str, Any] = {}
    profiler_agent_id: int | None = None
    scoped_tables: list[str] = []


class DBConnectionUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    db_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_config: dict[str, Any] | None = None
    profiler_agent_id: int | None = None
    scoped_tables: list[str] | None = None


class DBConnectionResponse(BaseModel):
    id: int
    name: str
    db_type: str
    host: str | None
    port: int | None
    db_name: str | None
    # username is shown; password is never returned
    ssl_config: dict[str, Any]
    profiler_agent_id: int | None = None
    scoped_tables: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceProfileResponse(BaseModel):
    id: int
    connection_id: int
    target_type: str | None = None
    catalog_name: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    row_count: int | None = None
    last_profiled_at: datetime
    profiled_by_agent_run_id: int | None = None
    columns: list[dict[str, Any]] = []
    candidate_relationships: list[dict[str, Any]] = []
    detected_layer: str | None = None
    prior_art_references: list[dict[str, Any]] = []
    unresolved_ambiguities: list[str] = []
    domain_inference: dict[str, Any] = {}
    timeseries_profile: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class SchemaIntrospectionResponse(BaseModel):
    tables: dict[str, list[str]]   # {"schema.table": ["col1", "col2"]}


# ── Git Connections ───────────────────────────────────────────────────────────

class GitConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    provider: str                           # "github" | "azure_devops"
    base_url: str | None = None
    organization: str | None = None
    default_project: str | None = None
    pat: str | None = None                  # plain text; encrypted before saving

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in GIT_PROVIDERS:
            raise ValueError(f"provider must be one of {GIT_PROVIDERS}")
        return v


class GitConnectionUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    organization: str | None = None
    default_project: str | None = None
    pat: str | None = None                  # plain text; re-encrypt if provided


class GitConnectionResponse(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str | None
    organization: str | None
    default_project: str | None
    pat_configured: bool = False            # True if pat_enc is set; token never returned
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Agents ────────────────────────────────────────────────────────────────────


class ToolAssignment(BaseModel):
    tool_name: str


class DBConnectionAssignment(BaseModel):
    db_connection_id: int
    allowed_tables: list[str] = []     # ["schema.table", ...]


class GitConnectionAssignment(BaseModel):
    git_connection_id: int


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    body: str = ""
    trigger_hints: list[str] = []


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    body: str | None = None
    trigger_hints: list[str] | None = None


class SkillResponse(BaseModel):
    id: int
    name: str
    description: str
    body: str
    trigger_hints: list[str]
    version: int
    is_active: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentSkillResponse(BaseModel):
    id: int
    agent_id: int
    skill_id: int
    position: int
    attached_at: datetime
    skill: SkillResponse

    model_config = {"from_attributes": True}


class SkillAssignment(BaseModel):
    skill_id: int


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    avatar: str | None = None           # emoji or image URL
    color: str | None = None            # hex colour for UI
    llm_connection_id: int | None = None
    prompt: str | None = None           # full system prompt written by admin
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8096
    is_orchestrator: bool = False
    visibility: str = "shared"
    status: str | None = "active"
    manifest: dict[str, Any] | None = None
    tools: list[ToolAssignment] = []
    db_connections: list[DBConnectionAssignment] = []
    git_connections: list[GitConnectionAssignment] = []
    skills: list[SkillAssignment] = []


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    avatar: str | None = None
    color: str | None = None
    llm_connection_id: int | None = None
    prompt: str | None = None
    model: str | None = None
    max_tokens: int | None = None
    is_orchestrator: bool | None = None
    visibility: str | None = None
    is_active: bool | None = None
    status: str | None = None
    manifest: dict[str, Any] | None = None
    tools: list[ToolAssignment] | None = None
    db_connections: list[DBConnectionAssignment] | None = None
    git_connections: list[GitConnectionAssignment] | None = None
    skills: list[SkillAssignment] | None = None


class AgentToolResponse(BaseModel):
    id: int
    tool_name: str

    model_config = {"from_attributes": True}


class AgentDBConnectionResponse(BaseModel):
    id: int
    db_connection_id: int
    allowed_tables: list[str]

    model_config = {"from_attributes": True}


class AgentGitConnectionResponse(BaseModel):
    id: int
    git_connection_id: int

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    id: int
    llm_connection_id: int | None
    name: str
    description: str | None
    avatar: str | None
    color: str | None
    prompt: str | None
    model: str | None
    max_tokens: int
    is_orchestrator: bool
    visibility: str
    is_active: bool
    status: str | None = "active"
    manifest: dict[str, Any] | None = None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    tools: list[AgentToolResponse] = []
    db_connections: list[AgentDBConnectionResponse] = []
    git_connections: list[AgentGitConnectionResponse] = []
    skills: list[AgentSkillResponse] = []

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Lightweight list item — no tools/db_connections details."""
    id: int
    llm_connection_id: int | None
    name: str
    description: str | None
    avatar: str | None
    color: str | None
    model: str | None
    is_orchestrator: bool
    visibility: str
    is_active: bool
    status: str | None = "active"
    tool_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Triggers ───────────────────────────────────────────────────────────────────

class TriggerCreate(BaseModel):
    agent_id: int
    trigger_type: TriggerType
    config: dict[str, Any] = {}
    is_active: bool = True


class TriggerUpdate(BaseModel):
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class TriggerResponse(BaseModel):
    id: int
    agent_id: int
    trigger_type: TriggerType
    config: dict[str, Any]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Tasks ──────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    agent_id: int
    metadata: dict[str, Any] = {}    # ticket title, repos, description, etc.


class TaskResponse(BaseModel):
    id: int
    agent_id: int
    trigger_id: int | None
    conversation_id: int | None
    status: TaskStatus
    trigger_source: str | None
    metadata: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if hasattr(obj, "metadata_"):
            # map ORM metadata_ → schema metadata
            data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
            data["metadata"] = obj.metadata_
            return cls(**{k: v for k, v in data.items() if k in cls.model_fields})
        return super().model_validate(obj, **kwargs)


# ── Conversations & Messages ───────────────────────────────────────────────────

class ConversationResponse(BaseModel):
    id: int
    task_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    source: str = "human"              # "agent" | "human" | "system"
    type: MessageType = MessageType.human
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = {}


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    source: str
    agent_id: int | None
    type: MessageType
    content: str
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if hasattr(obj, "metadata_"):
            data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
            data["metadata"] = obj.metadata_
            return cls(**{k: v for k, v in data.items() if k in cls.model_fields})
        return super().model_validate(obj, **kwargs)


# ── Context ───────────────────────────────────────────────────────────────────

class ContextEntryCreate(BaseModel):
    text: str = Field(..., min_length=1)
    tags: list[str] = []


class ContextEntryUpdate(BaseModel):
    text: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class BusinessContextEntryResponse(BaseModel):
    id: int
    text: str
    tags: list[str]
    version: int
    is_active: bool
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentContextEntryResponse(BaseModel):
    id: int
    agent_id: int
    text: str
    tags: list[str]
    version: int
    is_active: bool
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionResponse(BaseModel):
    id: int
    agent_id: int
    title: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str | None
    tool_name: str | None
    tool_result: dict[str, Any] | None
    tokens_used: int | None
    created_at: datetime
    # Swarm fields — identify which agent produced this message
    agent_name: str | None = None
    agent_color: str | None = None
    invocation_depth: int = 0

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    sandbox: bool = False   # True = don't persist, used by AgentBuilder test chat
    llm_connection_id: int | None = None
    context: dict[str, Any] | None = None


# ── Documents ─────────────────────────────────────────────────────────────────

class RagDocumentResponse(BaseModel):
    id: int
    filename: str
    mime_type: str | None
    size_bytes: int | None
    status: str
    chunk_count: int | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Skill catalog ─────────────────────────────────────────────────────────────

class SkillInfo(BaseModel):
    key: str
    name: str
    description: str
    is_async: bool
    input_schema: dict[str, Any]


# ── Budgets & Budget Statuses ──────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    scope_type: str = Field(..., max_length=50)
    scope_id: str = Field(..., max_length=100)
    period: str = Field(..., max_length=20)  # "daily" | "monthly"
    limit_amount: float
    warn_threshold_pct: int = 80
    on_exceeded: str = Field("alert_only", max_length=50)  # "alert_only" | "block_new_calls" | "block_and_pause_agent"
    is_active: bool = True


class BudgetUpdate(BaseModel):
    limit_amount: float | None = None
    warn_threshold_pct: int | None = None
    on_exceeded: str | None = None
    is_active: bool | None = None


class BudgetResponse(BaseModel):
    id: int
    scope_type: str
    scope_id: str
    period: str
    limit_amount: float
    warn_threshold_pct: int
    on_exceeded: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str | None

    model_config = {"from_attributes": True}


class BudgetStatusResponse(BaseModel):
    id: int
    scope_type: str
    scope_id: str
    period: str
    period_start: datetime
    period_end: datetime
    amount_spent: float
    status: str
    warning_fired_at_pct: int | None
    exceeded_fired: bool
    last_updated_at: datetime

    model_config = {"from_attributes": True}

