"""Pydantic schemas for LLM Call Logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class LlmCallLogListItemResponse(BaseModel):
    id: int
    agent_id: int
    agent_name: str | None = None
    session_id: int | None = None
    call_sequence_number: int
    created_at: datetime
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    summary: str | None = None

    model_config = {"from_attributes": True}


class LlmCallLogDetailResponse(BaseModel):
    id: int
    agent_id: int
    agent_name: str | None = None
    session_id: int | None = None
    call_sequence_number: int
    created_at: datetime
    model: str
    model_params: dict[str, Any] = {}
    system_prompt_base: str | None = None
    skills_available: list[dict[str, Any]] = []
    skills_injected: list[dict[str, Any]] = []
    message_history: list[dict[str, Any]] = []
    tools_available: list[dict[str, Any]] = []
    response_text: str | None = None
    response_tool_calls: list[dict[str, Any]] = []
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    model_config = {"from_attributes": True}
