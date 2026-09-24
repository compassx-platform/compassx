"""SQLAlchemy models for AI Gateway Model Context Protocol (MCP) servers and tools."""

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
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import AccountBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MCPServerType(str, enum.Enum):
    native = "native"          # Built-in CompassX tools (SQL Warehouse, Catalog Search, etc.)
    remote_sse = "remote_sse"  # HTTP SSE / Streamable remote MCP endpoint (e.g. GitHub, Jira, Slack)
    subprocess = "subprocess"  # Local CLI / container stdio tool execution


class MCPServer(AccountBase):
    """Model Context Protocol (MCP) Server configuration."""

    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    catalog_name = Column(String(255), nullable=True)
    schema_name = Column(String(255), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    server_type = Column(String(50), nullable=False, default="native")
    created_by = Column(String(255), nullable=True, default="system")

    # Remote SSE configuration
    endpoint_url = Column(Text, nullable=True)
    auth_config_enc = Column(Text, nullable=True)  # Encrypted headers/tokens (e.g. Bearer token)

    # Subprocess configuration
    command = Column(Text, nullable=True)          # e.g. "npx -y @modelcontextprotocol/server-postgres"
    env_vars_enc = Column(Text, nullable=True)     # Encrypted JSON map of environment variables

    # Discovery & State
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="true")
    cached_tools = Column(JSONB, default=list)     # Cached tool definitions from tools/list
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_mcp_servers_workspace_name", "workspace_id", "name", unique=True),
    )
