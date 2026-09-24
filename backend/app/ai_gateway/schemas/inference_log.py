"""Pydantic schemas for AI Gateway Inference and Tool Logs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InferenceLogResponse(BaseModel):
    id: int
    workspace_id: UUID | str | None
    user_id: UUID | str | None
    caller_type: str
    caller_id: str | None
    endpoint_id: int | None
    endpoint_name: str
    provider_type: str
    upstream_model_name: str
    request_messages: list[dict[str, Any]]
    tools_passed: list[dict[str, Any]] | None
    response_text: str | None
    response_tool_calls: list[dict[str, Any]] | None
    finish_reason: str | None
    input_tokens: int
    output_tokens: int
    total_cost: Decimal
    latency_ms: int
    status_code: int
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ToolLogResponse(BaseModel):
    id: int
    workspace_id: UUID | str | None
    user_id: UUID | str | None
    caller_id: str | None
    server_id: int | None
    server_name: str
    tool_name: str
    arguments: dict[str, Any] | None
    result: Any
    is_error: str
    error_message: str | None
    latency_ms: int
    created_at: datetime

    class Config:
        from_attributes = True
