"""SQLAlchemy models for the Agents module."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

import uuid
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base, AccountBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LLMProvider(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    azure = "azure"
    gemini = "gemini"
    bedrock = "bedrock"
    vertex = "vertex"
    ollama = "ollama"
    compatible = "compatible"
    litellm = "litellm"


class DBType(str, enum.Enum):
    postgres = "postgres"
    mysql = "mysql"
    mssql = "mssql"
    oracle = "oracle"
    sqlite = "sqlite"
    snowflake = "snowflake"
    bigquery = "bigquery"
    databricks = "databricks"


class AgentVisibility(str, enum.Enum):
    shared = "shared"
    private = "private"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class TriggerType(str, enum.Enum):
    ado_ticket_assigned = "ado_ticket_assigned"
    manual = "manual"
    schedule = "schedule"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    complete = "complete"
    failed = "failed"


class MessageType(str, enum.Enum):
    thinking = "thinking"
    plan = "plan"
    code = "code"
    test_result = "test_result"
    concern = "concern"
    output = "output"
    decision = "decision"
    human = "human"
    tool_call = "tool_call"
    system = "system"


class LLMConnection(AccountBase):
    __tablename__ = "llm_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    name = Column(Text, nullable=False)
    provider = Column(Enum(LLMProvider), nullable=False)
    model_name = Column(Text, nullable=False)
    api_key_enc = Column(Text, nullable=True)
    base_url = Column(Text, nullable=True)
    timeout_s = Column(Integer, nullable=False, default=120)
    max_tokens = Column(Integer, nullable=False, default=4096)
    config = Column(JSONB, default=dict)
    is_fallback = Column(Boolean, default=False)
    use_for_embedding = Column(Boolean, default=False, nullable=False, server_default="false")
    input_cost_per_1k_tokens = Column(Numeric(10, 4), nullable=True)
    output_cost_per_1k_tokens = Column(Numeric(10, 4), nullable=True)
    cost_currency = Column(String(3), server_default="USD", nullable=True)
    cost_configured_at = Column(DateTime(timezone=True), nullable=True)
    cost_configured_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class DBConnection(AccountBase):
    __tablename__ = "db_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    name = Column(Text, nullable=False)
    db_type = Column(Enum(DBType), nullable=False)
    host = Column(Text, nullable=True)
    port = Column(Integer, nullable=True)
    db_name = Column(Text, nullable=True)
    username_enc = Column(Text, nullable=True)
    password_enc = Column(Text, nullable=True)
    ssl_config = Column(JSONB, default=dict)
    profiler_agent_id = Column(Integer, nullable=True)
    scoped_tables = Column(JSONB, default=list, nullable=False, server_default='[]')
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = {"schema": "ai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    llm_connection_id = Column(Integer, nullable=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    avatar = Column(Text, nullable=True)
    color = Column(String(20), nullable=True)
    prompt = Column(Text, nullable=True)
    model = Column(Text, nullable=True, default="claude-sonnet-4-6")
    max_tokens = Column(Integer, nullable=False, default=8096)
    is_orchestrator = Column(Boolean, default=False)
    visibility = Column(Enum(AgentVisibility), nullable=False, default=AgentVisibility.shared)
    is_active = Column(Boolean, default=True)
    status = Column(String(50), server_default="active", nullable=True)
    manifest = Column(JSONB, nullable=True, default=dict)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    tools = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan")
    db_connections = relationship("AgentDBConnection", back_populates="agent", cascade="all, delete-orphan")
    git_connections = relationship("AgentGitConnection", back_populates="agent", cascade="all, delete-orphan")
    context_entries = relationship("AgentContextEntry", back_populates="agent", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="agent", cascade="all, delete-orphan")
    triggers = relationship("Trigger", back_populates="agent", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="agent", cascade="all, delete-orphan")
    skills = relationship("AgentSkillAttachment", back_populates="agent", cascade="all, delete-orphan")


class AgentTool(Base):
    __tablename__ = "agent_tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(String(100), nullable=False)

    agent = relationship("Agent", back_populates="tools")

    __table_args__ = (Index("idx_agent_tools_agent", "agent_id"), {"schema": "ai"})


class AgentDBConnection(Base):
    __tablename__ = "agent_db_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    db_connection_id = Column(Integer, nullable=False)
    allowed_tables = Column(JSONB, default=list)

    agent = relationship("Agent", back_populates="db_connections")

    __table_args__ = (Index("idx_agent_db_conn_agent", "agent_id"), {"schema": "ai"})


class GitConnection(AccountBase):
    __tablename__ = "git_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    name = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    base_url = Column(Text, nullable=True)
    organization = Column(Text, nullable=True)
    default_project = Column(Text, nullable=True)
    pat_enc = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class AgentGitConnection(Base):
    __tablename__ = "agent_git_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    git_connection_id = Column(Integer, nullable=False)

    agent = relationship("Agent", back_populates="git_connections")

    __table_args__ = (Index("idx_agent_git_connections_agent", "agent_id"), {"schema": "ai"})


class Trigger(Base):
    __tablename__ = "triggers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    trigger_type = Column(Enum(TriggerType), nullable=False)
    config = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    agent = relationship("Agent", back_populates="triggers")
    tasks = relationship("Task", back_populates="trigger", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_triggers_agent", "agent_id"), {"schema": "ai"})


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    trigger_id = Column(Integer, ForeignKey("ai.triggers.id", ondelete="SET NULL"), nullable=True)
    conversation_id = Column(Integer, nullable=True)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.pending)
    trigger_source = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    agent = relationship("Agent", back_populates="tasks")
    trigger = relationship("Trigger", back_populates="tasks")
    conversation = relationship("Conversation", back_populates="task", uselist=False, primaryjoin="Task.id == foreign(Conversation.task_id)")

    __table_args__ = (Index("idx_tasks_agent", "agent_id"), {"schema": "ai"})


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "ai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("ai.tasks.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    task = relationship("Task", back_populates="conversation", primaryjoin="Conversation.task_id == Task.id", foreign_keys="Conversation.task_id")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("ai.conversations.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(20), nullable=False)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="SET NULL"), nullable=True)
    type = Column(Enum(MessageType), nullable=False, default=MessageType.output)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (Index("idx_messages_conversation", "conversation_id"), {"schema": "ai"})


class BusinessContextEntry(Base):
    __tablename__ = "business_context_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text, nullable=False)
    tags = Column(JSONB, default=list)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_biz_ctx_active", "is_active"), {"schema": "ai"})


class AgentContextEntry(Base):
    __tablename__ = "agent_context_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    tags = Column(JSONB, default=list)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    agent = relationship("Agent", back_populates="context_entries")

    __table_args__ = (Index("idx_agent_ctx_agent_active", "agent_id", "is_active"), {"schema": "ai"})


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    summary_updated_at = Column(DateTime(timezone=True), nullable=True)
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    agent = relationship("Agent", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

    __table_args__ = (Index("idx_chat_sessions_agent", "workspace_id", "agent_id"), {"schema": "ai"})


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("ai.chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MessageRole, native_enum=False), nullable=False)
    content = Column(Text, nullable=True)
    tool_name = Column(String(100), nullable=True)
    tool_result = Column(JSONB, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    agent_name = Column(Text, nullable=True)
    agent_color = Column(String(20), nullable=True)
    invocation_depth = Column(Integer, nullable=False, server_default="0", default=0)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (Index("idx_chat_messages_session", "session_id"), {"schema": "ai"})


class RagDocument(Base):
    __tablename__ = "rag_documents"
    __table_args__ = {"schema": "ai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=True)
    session_id = Column(Integer, ForeignKey("ai.chat_sessions.id", ondelete="CASCADE"), nullable=True)
    filename = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.processing)
    chunk_count = Column(Integer, nullable=True)
    extracted_preview = Column(Text, nullable=True)  # first ~500 chars for chat chip display
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    chunks = relationship("RagChunk", back_populates="document", cascade="all, delete-orphan")


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("ai.rag_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)

    document = relationship("RagDocument", back_populates="chunks")

    __table_args__ = (Index("idx_rag_chunks_document", "document_id"), {"schema": "ai"})


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = {"schema": "ai"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    trigger_hints = Column(JSONB, default=list)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    agent_attachments = relationship("AgentSkillAttachment", back_populates="skill", cascade="all, delete-orphan")


class AgentSkillAttachment(Base):
    __tablename__ = "agent_skill_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(Integer, ForeignKey("ai.skills.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    attached_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="skills")
    skill = relationship("Skill", back_populates="agent_attachments")

    __table_args__ = (Index("idx_agent_skill_attachments_agent", "agent_id"), {"schema": "ai"})


class LlmCallLog(Base):
    __tablename__ = "llm_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("ai.chat_sessions.id", ondelete="SET NULL"), nullable=True)
    call_sequence_number = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    model = Column(Text, nullable=False)
    model_params = Column(JSONB, default=dict)

    # Prompt components
    system_prompt_base = Column(Text, nullable=True)
    skills_available = Column(JSONB, default=list)  # list of {skill_id, name, description}
    skills_injected = Column(JSONB, default=list)    # list of {skill_id, name, full_body}
    message_history = Column(JSONB, default=list)    # list of {role, message_id, content}
    tools_available = Column(JSONB, default=list)    # list of {name, description}

    # Response
    response_text = Column(Text, nullable=True)
    response_tool_calls = Column(JSONB, default=list)  # list of tool calls
    finish_reason = Column(String(50), nullable=True)

    # Token accounting
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    # Relationships
    agent = relationship("Agent")
    session = relationship("ChatSession")

    __table_args__ = (
        Index("idx_llm_call_logs_agent_session_created", "workspace_id", "agent_id", "session_id", "created_at"),
        {"schema": "ai"},
    )


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    scope_type = Column(String(50), nullable=False)
    scope_id = Column(String(100), nullable=False)
    period = Column(String(20), nullable=False)
    limit_amount = Column(Numeric(10, 4), nullable=False)
    warn_threshold_pct = Column(Integer, nullable=False, default=80, server_default="80")
    on_exceeded = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_budgets_scope", "workspace_id", "scope_type", "scope_id"),
        {"schema": "ai"},
    )


class BudgetStatus(Base):
    __tablename__ = "budget_statuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    scope_type = Column(String(50), nullable=False)
    scope_id = Column(String(100), nullable=False)
    period = Column(String(20), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    amount_spent = Column(Numeric(10, 4), nullable=False, default=0.0, server_default="0.0000")
    status = Column(String(20), nullable=False, default="ok", server_default="ok")
    warning_fired_at_pct = Column(Integer, nullable=True)
    exceeded_fired = Column(Boolean, nullable=False, default=False, server_default="false")
    last_updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_budget_statuses_uniq", "workspace_id", "scope_type", "scope_id", "period", "period_start", unique=True),
        {"schema": "ai"},
    )


class DataSourceProfile(Base):
    __tablename__ = "data_source_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, nullable=True)
    target_type = Column(String(50), nullable=False, server_default="table")
    catalog_name = Column(Text, nullable=True)
    schema_name = Column(Text, nullable=True)
    table_name = Column(Text, nullable=True)
    row_count = Column(Integer, nullable=True)
    last_profiled_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    profiled_by_agent_run_id = Column(Integer, nullable=True)

    # Profiling data stored as JSONB blobs
    columns = Column(JSONB, default=list, nullable=False, server_default='[]')
    candidate_relationships = Column(JSONB, default=list, nullable=False, server_default='[]')
    detected_layer = Column(String(50), nullable=True)
    prior_art_references = Column(JSONB, default=list, nullable=False, server_default='[]')
    unresolved_ambiguities = Column(JSONB, default=list, nullable=False, server_default='[]')
    timeseries_profile = Column(JSONB, default=dict, nullable=False, server_default='{}')
    domain_inference = Column(JSONB, default=dict, nullable=False, server_default='{}')



    __table_args__ = (
        Index(
            "idx_ds_profile_conn_target",
            "connection_id",
            "target_type",
            "catalog_name",
            "schema_name",
            "table_name",
            unique=True,
        ),
    )


class ResearchEngineRun(Base):
    __tablename__ = "research_engine_runs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    workspace_id = Column(Text, nullable=False, default="default")
    agent_id = Column(Integer, ForeignKey("ai.agents.id", ondelete="SET NULL"), nullable=True)
    trigger_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    context_package = Column(JSONB, nullable=False, default=dict)
    changes_since_last_run = Column(JSONB, nullable=False, default=list)
    maturity_assessment = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_research_engine_runs_workspace_started", "workspace_id", "started_at"),
        {"schema": "ai"},
    )


class ResearchProposal(Base):
    __tablename__ = "research_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True)
    workspace_id = Column(Text, nullable=False, default="default")
    engine_run_id = Column(UUID(as_uuid=True), ForeignKey("ai.research_engine_runs.id", ondelete="SET NULL"), nullable=True)
    status = Column(Text, nullable=False, default="proposed")
    problem_statement = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=True)
    maturity_level = Column(Text, nullable=False)
    priority_rank = Column(Integer, nullable=False)
    priority_rationale = Column(Text, nullable=True)
    data_evidence = Column(JSONB, nullable=False, default=list)
    proposed_deliverables = Column(JSONB, nullable=False, default=list)
    implementation_sequence = Column(JSONB, nullable=False, default=list)
    dependencies = Column(JSONB, nullable=False, default=list)
    open_questions = Column(JSONB, nullable=False, default=list)
    domain_gotchas = Column(JSONB, nullable=False, default=list)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Text, nullable=True)
    implementation_agent_run_id = Column(Text, nullable=True)
    implemented_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_research_proposals_workspace_status", "workspace_id", "status"),
        Index("idx_research_proposals_run_rank", "engine_run_id", "priority_rank"),
        {"schema": "ai"},
    )


class ResearchProposalMessage(Base):
    __tablename__ = "research_proposal_messages"

    id = Column(UUID(as_uuid=True), primary_key=True)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("ai.research_proposals.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_research_proposal_messages_proposal", "proposal_id", "created_at"),
        {"schema": "ai"},
    )


# ── Change Records (Part G5 — Session Artifact Visibility) ────────────────────

class ChangeRecord(Base):
    """Captures before/after content for every notebook/file edit or create tool call.

    Written at edit-tool execution time (D16).  Supports Accept/Reject post-hoc
    review without blocking the build (D20).
    """
    __tablename__ = "change_records"
    __table_args__ = (
        Index("idx_change_records_session", "session_id", "captured_at"),
        Index("idx_change_records_plan_step", "plan_id", "step_id"),
        {"schema": "ai"},
    )

    change_id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    session_id = Column(Integer, ForeignKey("ai.chat_sessions.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(Text, nullable=False)          # catalog.schema.object
    object_type = Column(String(50), nullable=False)  # notebook | table | dashboard | query | …
    before_content = Column(Text, nullable=True)      # None for creates
    after_content = Column(Text, nullable=True)
    additions = Column(Integer, nullable=False, default=0)
    deletions = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending_review")
    # Link fields (optional — set when part of a plan step)
    step_id = Column(Integer, nullable=True)
    plan_id = Column(String(36), nullable=True)
    # For revert records: change_id of the original change this reverts
    reverted_by_change_id = Column(String(36), nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class NovaAttachment(Base):
    """Uploaded session-scoped file attachment for Nova."""
    __tablename__ = "nova_attachments"
    __table_args__ = (
        Index("idx_nova_attachments_session", "session_id"),
        {"schema": "ai"},
    )

    file_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(Integer, ForeignKey("ai.chat_sessions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    blob_path = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="processing")  # processing | ready | failed | purged
    delivery_mode = Column(Text, nullable=True)                  # inline | tool_fetch | multimodal_native
    extracted_token_count = Column(Integer, nullable=True)
    extraction_error = Column(Text, nullable=True)
    promoted_object_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by = Column(String(255), nullable=False, default="default_user")

    preview = relationship("NovaAttachmentPreview", back_populates="attachment", uselist=False, cascade="all, delete-orphan")


class NovaAttachmentPreview(Base):
    """Truncated preview text and full extracted text blob reference for tool_fetch files."""
    __tablename__ = "nova_attachment_previews"
    __table_args__ = {"schema": "ai"}

    file_id = Column(UUID(as_uuid=True), ForeignKey("ai.nova_attachments.file_id", ondelete="CASCADE"), primary_key=True)
    preview_text = Column(Text, nullable=True)
    full_text_blob_path = Column(Text, nullable=True)

    attachment = relationship("NovaAttachment", back_populates="preview")

