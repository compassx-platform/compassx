"""SQLAlchemy models for AI Gateway Providers and Model Endpoints."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import AccountBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIProviderType(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    azure = "azure"
    gemini = "gemini"
    bedrock = "bedrock"
    vertex = "vertex"
    ollama = "ollama"
    compatible = "compatible"


class AIProvider(AccountBase):
    """External AI model vendor / provider configuration."""

    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    catalog_name = Column(String(255), nullable=True)
    schema_name = Column(String(255), nullable=True)
    name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False)
    api_key_enc = Column(Text, nullable=True)
    base_url = Column(Text, nullable=True)
    config = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(255), nullable=True, default="system")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    endpoints = relationship("AIModelEndpoint", back_populates="provider", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ai_providers_workspace_name", "workspace_id", "name", unique=True),
    )


class AIModelEndpoint(AccountBase):
    """Governed model endpoint with routing, rate limiting, and failover support."""

    __tablename__ = "ai_model_endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)  # Endpoint alias, e.g. "gpt-4o", "default-chat"
    provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False)
    upstream_model_name = Column(String(100), nullable=False)  # e.g. "gpt-4o-2024-08-06", "claude-3-5-sonnet-20241022"

    # Routing & Failover
    fallback_endpoint_ids = Column(ARRAY(Integer), default=list)
    timeout_s = Column(Integer, default=120, nullable=False)
    max_tokens = Column(Integer, default=8192, nullable=False)
    temperature_default = Column(Numeric(3, 2), default=0.7, nullable=True)

    # Rate Limiting & Cost Control
    rate_limit_rpm = Column(Integer, nullable=True)  # Requests per minute limit
    rate_limit_tpm = Column(Integer, nullable=True)  # Tokens per minute limit
    input_cost_per_1k_tokens = Column(Numeric(10, 4), nullable=True)
    output_cost_per_1k_tokens = Column(Numeric(10, 4), nullable=True)
    cost_currency = Column(String(3), server_default="USD", default="USD", nullable=True)

    # Capabilities & Governance
    use_for_embedding = Column(Boolean, default=False, nullable=False, server_default="false")
    is_default = Column(Boolean, default=False, nullable=False, server_default="false")
    guardrail_config = Column(JSONB, default=dict)  # e.g. {"pii_masking": true, "block_toxic": true}
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    provider = relationship("AIProvider", back_populates="endpoints")

    __table_args__ = (
        Index("idx_ai_endpoints_workspace_name", "workspace_id", "name", unique=True),
    )
