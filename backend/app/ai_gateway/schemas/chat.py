"""Pydantic schemas for OpenAI-compatible Chat, Models, and Embeddings API."""

from __future__ import annotations

import time
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


# --- Chat Completion Request & Message Types ---

class FunctionCall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    arguments: str


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    content: str | list[Any] | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ToolDefinitionFunction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["function"] = "function"
    function: ToolDefinitionFunction


def serialize_tools(tools: list[Any] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    dumped: list[dict[str, Any]] = []
    for tool in tools:
        if hasattr(tool, "model_dump"):
            dumped.append(tool.model_dump(exclude_none=True))
        elif isinstance(tool, dict):
            dumped.append(tool)
    return dumped or None


def function_tool_specs(tools: list[Any] | None) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for tool in serialize_tools(tools) or []:
        kind = str(tool.get("type") or "function")
        if kind != "function":
            continue
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        specs.append({
            "name": name,
            "description": str(function.get("description") or ""),
            "parameters": function.get("parameters") or {"type": "object", "properties": {}},
        })
    return specs


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str = Field(..., description="Target model endpoint name or alias")
    messages: list[ChatMessage]
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    stop: str | list[str] | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    user: str | None = None


# --- Chat Completion Response Types ---

class ChatCompletionMessage(BaseModel):
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str | None = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)


# --- Streaming Chunk Types ---

class ChatCompletionDelta(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChunkChoice]
    usage: ChatCompletionUsage | None = None


# --- Embeddings Types ---

class EmbeddingRequest(BaseModel):
    model: str = Field(..., description="Target embedding model endpoint name")
    input: str | list[str] = Field(..., description="Input text or array of strings")
    user: str | None = None


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)


# --- Model List Types ---

class ModelItem(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "compassx"
    provider_type: str | None = None
    is_default: bool = False
    use_for_embedding: bool = False


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelItem]
