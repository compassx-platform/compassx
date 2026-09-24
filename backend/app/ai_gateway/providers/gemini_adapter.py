"""Google Gemini Provider Adapter."""

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


class GeminiAdapter(BaseProviderAdapter):
    """Adapter for Google Gemini models (e.g. gemini-2.5-flash, gemini-1.5-pro)."""

    def _get_base_url(self, creds: ProviderCredentials) -> str:
        return (creds.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def _convert_messages(self, request: ChatCompletionRequest) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        system_instruction = None
        contents = []

        system_parts = []
        for msg in request.messages:
            if msg.role == "system":
                if msg.content:
                    system_parts.append(msg.content)
            elif msg.role in ("user", "assistant"):
                role = "user" if msg.role == "user" else "model"
                parts = []
                if msg.content:
                    parts.append({"text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        except Exception:
                            args = {}
                        parts.append({
                            "functionCall": {
                                "name": tc.function.name,
                                "args": args,
                            }
                        })
                contents.append({"role": role, "parts": parts})
            elif msg.role == "tool":
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.name or "tool_result",
                            "response": {"content": msg.content or ""},
                        }
                    }]
                })

        if system_parts:
            system_instruction = {"parts": [{"text": "\n\n".join(system_parts)}]}

        return system_instruction, contents

    def _convert_tools(self, request: ChatCompletionRequest) -> list[dict[str, Any]] | None:
        if not request.tools:
            return None
        declarations = []
        for t in request.tools:
            if t.type == "function":
                declarations.append({
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "parameters": t.function.parameters or {"type": "object", "properties": {}},
                })
        return [{"functionDeclarations": declarations}] if declarations else None

    async def chat_stream(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> AsyncIterator[ChatCompletionChunk]:
        base_url = self._get_base_url(creds)
        api_key = creds.api_key or ""
        system_instruction, contents = self._convert_messages(request)
        tools = self._convert_tools(request)

        url = f"{base_url}/models/{upstream_model}:streamGenerateContent?alt=sse&key={api_key}"

        payload: dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if tools:
            payload["tools"] = tools

        call_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    raise RuntimeError(f"Gemini API error ({response.status_code}): {error_body.decode(errors='replace')}")

                tool_index = 0
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                    except Exception:
                        continue

                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    candidate = candidates[0]
                    content = candidate.get("content", {})
                    parts = content.get("parts", [])

                    for part in parts:
                        if "text" in part:
                            yield ChatCompletionChunk(
                                id=call_id,
                                model=upstream_model,
                                created=created,
                                choices=[ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionDelta(content=part["text"]),
                                )],
                            )
                        elif "functionCall" in part:
                            fc = part["functionCall"]
                            yield ChatCompletionChunk(
                                id=call_id,
                                model=upstream_model,
                                created=created,
                                choices=[ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionDelta(
                                        tool_calls=[{
                                            "index": tool_index,
                                            "id": f"call_{uuid.uuid4().hex[:8]}",
                                            "type": "function",
                                            "function": {
                                                "name": fc.get("name", ""),
                                                "arguments": json.dumps(fc.get("args", {})),
                                            },
                                        }]
                                    ),
                                )],
                            )
                            tool_index += 1

    async def chat_complete(
        self,
        request: ChatCompletionRequest,
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> ChatCompletionResponse:
        base_url = self._get_base_url(creds)
        api_key = creds.api_key or ""
        system_instruction, contents = self._convert_messages(request)
        tools = self._convert_tools(request)

        url = f"{base_url}/models/{upstream_model}:generateContent?key={api_key}"

        payload: dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if tools:
            payload["tools"] = tools

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            content_text = ""
            tool_calls = []

            if candidates:
                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                for part in parts:
                    if "text" in part:
                        content_text += part["text"]
                    elif "functionCall" in part:
                        fc = part["functionCall"]
                        tool_calls.append(ToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            type="function",
                            function=FunctionCall(
                                name=fc.get("name", ""),
                                arguments=json.dumps(fc.get("args", {})),
                            ),
                        ))

            usage_meta = data.get("usageMetadata", {})
            prompt_tokens = usage_meta.get("promptTokenCount", 0)
            candidates_tokens = usage_meta.get("candidatesTokenCount", 0)

            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
                model=upstream_model,
                choices=[ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=content_text if content_text else None,
                        tool_calls=tool_calls if tool_calls else None,
                    ),
                    finish_reason="tool_calls" if tool_calls else "stop",
                )],
                usage=ChatCompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=candidates_tokens,
                    total_tokens=prompt_tokens + candidates_tokens,
                ),
            )

    async def embed(
        self,
        texts: list[str],
        creds: ProviderCredentials,
        upstream_model: str,
    ) -> list[list[float]]:
        base_url = self._get_base_url(creds)
        api_key = creds.api_key or ""
        url = f"{base_url}/models/{upstream_model}:batchEmbedContents?key={api_key}"

        requests = [{"model": f"models/{upstream_model}", "content": {"parts": [{"text": t}]}} for t in texts]
        payload = {"requests": requests}

        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"Gemini embedding error ({resp.status_code}): {resp.text}")
            data = resp.json()
            return [emb.get("values", []) for emb in data.get("embeddings", [])]

    async def ping(
        self,
        creds: ProviderCredentials,
        sample_model: str | None = None,
    ) -> tuple[bool, str, list[str]]:
        if not creds.api_key:
            return False, "Please enter an API key to discover live models from Google Gemini", []

        base_url = self._get_base_url(creds)
        api_key = creds.api_key or ""
        url = f"{base_url}/models?key={api_key}"
        timeout = httpx.Timeout(10.0, connect=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
                    return True, "Successfully connected to Google Gemini API", models[:20]
                else:
                    return False, f"Gemini returned HTTP {resp.status_code}: {resp.text[:200]}", []
        except Exception as e:
            return False, f"Connection failed: {str(e)}", []
