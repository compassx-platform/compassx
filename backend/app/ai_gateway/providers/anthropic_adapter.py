"""Anthropic Claude Provider Adapter."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

import httpx

from app.ai_gateway.providers.base import BaseProviderAdapter, ProviderCredentials
from app.ai_gateway.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionDelta,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    FunctionCall,
    ToolCall,
)

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseProviderAdapter):
    """Adapter for Anthropic Claude models (e.g. Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.7 Sonnet)."""

    def _get_base_url(self, creds: ProviderCredentials) -> str:
        return (creds.base_url or "https://api.anthropic.com/v1").rstrip("/")

    def _get_headers(self, creds: ProviderCredentials) -> dict[str, str]:
        version = creds.config.get("anthropic_version", "2023-06-01")
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": version,
        }
        if creds.api_key:
            headers["x-api-key"] = creds.api_key
        return headers

    def _convert_messages_and_system(self, request: ChatCompletionRequest) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts = []
        anthropic_messages = []

        for msg in request.messages:
            if msg.role == "system":
                if msg.content:
                    system_parts.append(msg.content)
            elif msg.role == "user":
                anthropic_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                if msg.tool_calls:
                    content_blocks = []
                    if msg.content:
                        content_blocks.append({"type": "text", "text": msg.content})
                    for tc in msg.tool_calls:
                        try:
                            input_dict = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        except Exception:
                            input_dict = {}
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": input_dict,
                        })
                    anthropic_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    anthropic_messages.append({"role": "assistant", "content": msg.content or ""})
            elif msg.role == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "call_unknown",
                        "content": msg.content or "",
                    }],
                })

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, anthropic_messages

    def _convert_tools(self, request: ChatCompletionRequest) -> list[dict[str, Any]] | None:
        if not request.tools:
            return None
        tools = []
        for t in request.tools:
            if t.type == "function":
                tools.append({
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "input_schema": t.function.parameters or {"type": "object", "properties": {}},
                })
        return tools if tools else None

    async def chat_stream(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> AsyncIterator[ChatCompletionChunk]:
        base_url = self._get_base_url(creds)
        headers = self._get_headers(creds)
        system_prompt, messages = self._convert_messages_and_system(request)
        tools = self._convert_tools(request)

        payload: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        call_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream("POST", f"{base_url}/messages", headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    error_text = error_body.decode(errors="replace")
                    raise RuntimeError(f"Anthropic API error ({response.status_code}): {error_text}")

                current_tool_id = None
                current_tool_name = None
                tool_index = 0

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    try:
                        event = json.loads(data_str)
                    except Exception:
                        continue

                    event_type = event.get("type")

                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            current_tool_id = block.get("id")
                            current_tool_name = block.get("name")
                            yield ChatCompletionChunk(
                                id=call_id,
                                model=upstream_model,
                                created=created,
                                choices=[ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionDelta(
                                        tool_calls=[{
                                            "index": tool_index,
                                            "id": current_tool_id,
                                            "type": "function",
                                            "function": {"name": current_tool_name, "arguments": ""},
                                        }]
                                    ),
                                )],
                            )
                            tool_index += 1

                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield ChatCompletionChunk(
                                id=call_id,
                                model=upstream_model,
                                created=created,
                                choices=[ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionDelta(content=delta.get("text")),
                                )],
                            )
                        elif delta.get("type") == "input_json_delta":
                            yield ChatCompletionChunk(
                                id=call_id,
                                model=upstream_model,
                                created=created,
                                choices=[ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionDelta(
                                        tool_calls=[{
                                            "index": max(0, tool_index - 1),
                                            "function": {"arguments": delta.get("partial_json", "")},
                                        }]
                                    ),
                                )],
                            )

                    elif event_type == "message_delta":
                        delta = event.get("delta", {})
                        stop_reason = delta.get("stop_reason")
                        finish = "tool_calls" if stop_reason == "tool_use" else "stop"
                        usage = event.get("usage")
                        usage_obj = None
                        if usage:
                            usage_obj = ChatCompletionUsage(
                                prompt_tokens=0,
                                completion_tokens=usage.get("output_tokens", 0),
                                total_tokens=usage.get("output_tokens", 0),
                            )
                        yield ChatCompletionChunk(
                            id=call_id,
                            model=upstream_model,
                            created=created,
                            choices=[ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionDelta(),
                                finish_reason=finish,
                            )],
                            usage=usage_obj,
                        )

    async def chat_complete(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> ChatCompletionResponse:
        base_url = self._get_base_url(creds)
        headers = self._get_headers(creds)
        system_prompt, messages = self._convert_messages_and_system(request)
        tools = self._convert_tools(request)

        payload: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = tools
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.post(f"{base_url}/messages", headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"Anthropic API error ({resp.status_code}): {resp.text}")

            data = resp.json()
            content_text = ""
            tool_calls = []

            for block in data.get("content", []):
                if block.get("type") == "text":
                    content_text += block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        type="function",
                        function=FunctionCall(
                            name=block.get("name", ""),
                            arguments=json.dumps(block.get("input", {})),
                        ),
                    ))

            stop_reason = data.get("stop_reason")
            finish_reason = "tool_calls" if stop_reason == "tool_use" else "stop"
            usage_dict = data.get("usage", {})

            return ChatCompletionResponse(
                id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
                model=upstream_model,
                choices=[ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=content_text if content_text else None,
                        tool_calls=tool_calls if tool_calls else None,
                    ),
                    finish_reason=finish_reason,
                )],
                usage=ChatCompletionUsage(
                    prompt_tokens=usage_dict.get("input_tokens", 0),
                    completion_tokens=usage_dict.get("output_tokens", 0),
                    total_tokens=usage_dict.get("input_tokens", 0) + usage_dict.get("output_tokens", 0),
                ),
            )

    async def embed(
        self,
        texts: list[str],
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not offer a native embedding endpoint; use Voyage AI or OpenAI.")

    async def ping(
        self,
        creds: ProviderCredentials,
        sample_model: str | None = None,
    ) -> tuple[bool, str, list[str]]:
        if not creds.api_key:
            return False, "Please enter an API key to discover live models from Anthropic", []

        base_url = self._get_base_url(creds)
        headers = self._get_headers(creds)
        timeout = httpx.Timeout(10.0, connect=5.0)

        # 1. Try GET /models endpoint
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                models_resp = await client.get(f"{base_url}/models", headers=headers)
                if models_resp.status_code == 200:
                    data = models_resp.json()
                    model_ids = [
                        m.get("id")
                        for m in data.get("data", [])
                        if isinstance(m, dict) and m.get("id")
                    ]
                    if model_ids:
                        return True, "Successfully connected to Anthropic API", model_ids
        except Exception:
            pass

        # 2. Fallback to minimal 1-token message test
        payload = {
            "model": sample_model or "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.post(f"{base_url}/messages", headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    return True, "Successfully connected to Anthropic API", [
                        "claude-3-7-sonnet-20250219",
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-20241022",
                        "claude-3-opus-20240229",
                    ]
                elif resp.status_code in (401, 403):
                    return False, "Invalid Anthropic API key or unauthorized (HTTP 401/403)", []
                else:
                    return False, f"Anthropic returned HTTP {resp.status_code}: {resp.text[:200]}", []
        except Exception as e:
            return False, f"Connection failed: {str(e)}", []
