"""SQLAlchemy models for AI Gateway Inference and Tool Execution Logs."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import SystemBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIGatewayInferenceLog(SystemBase):
    """Logs model inference requests, streaming chunks, latency, and token consumption."""

    __tablename__ = "ai_gateway_inference_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    user_id = Column(UUID(as_uuid=False), nullable=True)
    caller_type = Column(String(50), nullable=False, default="direct_api")  # "agent", "nova", "notebook", "direct_api"
    caller_id = Column(String(100), nullable=True)

    endpoint_id = Column(Integer, nullable=True)
    endpoint_name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False)
    upstream_model_name = Column(String(100), nullable=False)

    # Request / Response Payloads
    request_messages = Column(JSONB, nullable=False, default=list)
    tools_passed = Column(JSONB, nullable=True)
    response_text = Column(Text, nullable=True)
    response_tool_calls = Column(JSONB, nullable=True)
    finish_reason = Column(String(50), nullable=True)

    # Telemetry & Cost
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    total_cost = Column(Numeric(10, 6), default=0, nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    status_code = Column(Integer, default=200, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_gateway_logs_workspace_created", "workspace_id", "created_at"),
        Index("idx_gateway_logs_endpoint_created", "endpoint_name", "created_at"),
    )


class AIGatewayToolLog(SystemBase):
    """Audit log for MCP and native tool executions executed through the AI Gateway."""

    __tablename__ = "ai_gateway_tool_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), nullable=True)
    user_id = Column(UUID(as_uuid=False), nullable=True)
    caller_id = Column(String(100), nullable=True)

    server_id = Column(Integer, nullable=True)
    server_name = Column(String(100), nullable=False)
    tool_name = Column(String(100), nullable=False)

    arguments = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)
    is_error = Column(String(10), default="false", nullable=False)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_gateway_tool_logs_workspace_created", "workspace_id", "created_at"),
        Index("idx_gateway_tool_logs_tool_name", "tool_name", "created_at"),
    )
