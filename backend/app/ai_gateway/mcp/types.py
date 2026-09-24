"""MCP (Model Context Protocol) Data Types and JSON-RPC Schemas."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: JSONRPCError | None = None


class MCPToolInputSchema(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class MCPTool(BaseModel):
    name: str
    description: str | None = None
    inputSchema: MCPToolInputSchema | dict[str, Any] = Field(default_factory=dict)


class MCPToolContent(BaseModel):
    type: Literal["text", "image", "resource"] = "text"
    text: str | None = None
    data: str | None = None
    mimeType: str | None = None


class MCPToolResult(BaseModel):
    content: list[MCPToolContent] = Field(default_factory=list)
    isError: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)
