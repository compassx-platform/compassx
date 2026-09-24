"""Pydantic schemas for AI Gateway MCP Servers and Tool Execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai_gateway.models.mcp import MCPServerType


class MCPServerCreate(BaseModel):
    catalog_name: str | None = None
    schema_name: str | None = None
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    server_type: MCPServerType = MCPServerType.native
    endpoint_url: str | None = None
    auth_headers: dict[str, str] | None = None  # Transformed to encrypted auth_config_enc
    command: str | None = None
    env_vars: dict[str, str] | None = None      # Transformed to encrypted env_vars_enc
    is_enabled: bool = True


class MCPServerUpdate(BaseModel):
    catalog_name: str | None = None
    schema_name: str | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    server_type: MCPServerType | None = None
    endpoint_url: str | None = None
    auth_headers: dict[str, str] | None = None
    command: str | None = None
    env_vars: dict[str, str] | None = None
    is_enabled: bool | None = None


class MCPToolDefinition(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    server_id: int | None = None
    server_name: str | None = None


class MCPServerResponse(BaseModel):
    id: int
    workspace_id: UUID | str | None
    catalog_name: str | None = None
    schema_name: str | None = None
    full_name: str | None = None
    name: str
    description: str | None
    server_type: MCPServerType
    endpoint_url: str | None
    has_auth: bool
    command: str | None
    is_enabled: bool
    created_by: str | None = None
    cached_tools: list[dict[str, Any]]
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MCPServerSyncResponse(BaseModel):
    server_id: int
    server_name: str
    tools_count: int
    tools: list[MCPToolDefinition]
    synced_at: datetime


class MCPToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Qualified or un-qualified tool name")
    arguments: dict[str, Any] = Field(default_factory=dict)
    server_id: int | str | None = None
    caller_id: str | None = None


class MCPToolCallResponse(BaseModel):
    tool_name: str
    server_name: str
    result: Any
    is_error: bool = False
    error_message: str | None = None
    latency_ms: int = 0
