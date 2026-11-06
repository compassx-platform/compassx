"""OpenAI-Compatible Ingress Proxy Routes for AI Gateway."""

from __future__ import annotations

import json

import logging

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request

from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from app.ai_gateway.models.provider import AIModelEndpoint, AIProvider

from app.ai_gateway.schemas.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelItem,
    ModelListResponse,
)

from app.ai_gateway.services.gateway_service import GatewayService

from app.database import get_account_db, SystemSessionLocal

from app.models.app import App

logger = logging.getLogger("app.ai_gateway.routes.proxy_routes")
def _get_workspace_id(request: Request) -> str | None:
    ctx = getattr(request.state, "workspace", None)
    if ctx and hasattr(ctx, "workspace_id"):
        try:
            import uuid
            uuid.UUID(str(ctx.workspace_id))
            return str(ctx.workspace_id)
        except Exception:
            return None
    ws_header = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id")
    if ws_header:
        try:
            import uuid
            uuid.UUID(str(ws_header))
            return str(ws_header)
        except Exception:
            return None
    return None

def _resolve_caller_and_workspace(request: Request) -> tuple[str | None, str, str | None]:
    """
    Resolve (workspace_id, caller_type, caller_id) from the request.

    Workspace sandboxes send Authorization: Bearer cx_gw_ws_<secret>.
    Older sandboxes still send cx_gw_app_<app_id>.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:].strip()
        if raw_token.startswith("cx_gw_ws_"):
            from app.services.sandbox_credentials import workspace_id_for_gateway_token
            ws_id = workspace_id_for_gateway_token(raw_token)
            if not ws_id:
                raise HTTPException(status_code=401, detail="Invalid gateway token.")
            return (ws_id, "dev_agent", ws_id)
        if raw_token.startswith("cx_gw_app_"):
            token_body = raw_token[len("cx_gw_app_"):]
            if token_body.startswith("app_"):
                parts = token_body.split("_")
                app_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else token_body
            else:
                app_id = token_body.split("_")[0]

            with SystemSessionLocal() as sys_db:
                app = sys_db.query(App).filter(App.id == app_id).first()
                if not app:
                    raise HTTPException(status_code=401, detail=f"Invalid App Gateway Token: app '{app_id}' not found.")
                if getattr(app, "status", None) == "archived":
                    raise HTTPException(status_code=403, detail="Application is archived.")
                ws_id = str(app.workspace_id) if app.workspace_id else None
                return (ws_id, "dev_agent", app.id)

    workspace_id = _get_workspace_id(request)
    user_id = request.headers.get("X-User-Id") or None
    return (workspace_id, "direct_api", user_id)

async def _sse_chunk_generator(stream_iter: AsyncIterator[ChatCompletionChunk]) -> AsyncIterator[str]:
    """Format ChatCompletionChunk objects into standard SSE data chunks."""
    try:
        async for chunk in stream_iter:
            chunk_json = chunk.model_dump_json(exclude_none=True)
            yield f"data: {chunk_json}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error("Error during streaming SSE generation: %s", e)
        err_payload = json.dumps({"error": {"message": str(e), "type": "gateway_error"}})
        yield f"data: {err_payload}\n\n"
        yield "data: [DONE]\n\n"

def _response_text(content: Any) -> str:
    if content is None or isinstance(content, str):
        return content or ""
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("output_text") or ""))
        return "\n".join(part for part in parts if part)
    return str(content)

def _chat_request_from_responses(payload: dict[str, Any]) -> ChatCompletionRequest:
    """Translate an OpenAI Responses request into a chat completion."""
    messages: list[dict[str, Any]] = []
    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions})

    raw_input = payload.get("input")
    if isinstance(raw_input, str):
        messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        for item in raw_input:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind == "function_call":
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": item.get("call_id") or item.get("id") or "call",
                        "type": "function",
                        "function": {
                            "name": item.get("name") or "",
                            "arguments": item.get("arguments") or "{}",
                        },
                    }],
                })
            elif kind == "function_call_output":
                messages.append({
                    "role": "tool",
                    "tool_call_id": item.get("call_id") or "",
                    "content": _response_text(item.get("output")),
                })
            elif item.get("role"):
                messages.append({
                    "role": item["role"],
                    "content": _response_text(item.get("content")),
                })

    tools = []
    for tool in payload.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") not in (None, "function"):
            continue
        function = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = function.get("name")
        if not name:
            continue
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": function.get("description"),
                "parameters": function.get("parameters") or {"type": "object", "properties": {}},
            },
        })

    return ChatCompletionRequest(
        model=str(payload.get("model") or ""),
        messages=messages or [{"role": "user", "content": ""}],
        tools=tools or None,
        temperature=payload.get("temperature"),
        top_p=payload.get("top_p"),
        max_completion_tokens=payload.get("max_output_tokens") or payload.get("max_completion_tokens"),
        stream=bool(payload.get("stream")),
        user=payload.get("user"),
    )

def _sse_event(payload: dict[str, Any]) -> str:
    return f"event: {payload['type']}\ndata: {json.dumps(payload)}\n\n"

async def _responses_event_stream(stream_iter: AsyncIterator[ChatCompletionChunk], model: str) -> AsyncIterator[str]:
    """Emit the Responses stream events OpenCode's OpenAI client consumes."""
    import uuid

    response_id = f"resp_{uuid.uuid4().hex}"
    sequence = 0

    def event(payload: dict[str, Any]) -> str:
        nonlocal sequence
        payload["sequence_number"] = sequence
        sequence += 1
        return _sse_event(payload)

    text_parts: list[str] = []
    tools: dict[int, dict[str, str]] = {}
    message_open = False
    message_id = f"msg_{uuid.uuid4().hex}"

    def open_message() -> str:
        nonlocal message_open
        if message_open:
            return ""
        message_open = True
        return (
            event({
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": message_id,
                    "type": "message",
                    "status": "in_progress",
                    "role": "assistant",
                    "content": [],
                },
            })
            + event({
                "type": "response.content_part.added",
                "item_id": message_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            })
        )

    yield event({
        "type": "response.created",
        "response": {
            "id": response_id,
            "object": "response",
            "status": "in_progress",
            "model": model,
            "output": [],
        },
    })
    try:
        async for chunk in stream_iter:
            for choice in chunk.choices or []:
                delta = choice.delta
                if delta.content:
                    text_parts.append(delta.content)
                    yield open_message()
                    yield event({
                        "type": "response.output_text.delta",
                        "item_id": message_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": delta.content,
                    })
                for call in delta.tool_calls or []:
                    index = int(call.get("index") or 0)
                    state = tools.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if call.get("id"):
                        state["id"] = str(call["id"])
                    function = call.get("function") or {}
                    if function.get("name"):
                        state["name"] = str(function["name"])
                    if function.get("arguments"):
                        state["arguments"] += str(function["arguments"])
    except Exception as exc:
        logger.error("Responses stream failed: %s", exc)
        yield event({"type": "error", "error": {"message": str(exc), "type": "gateway_error"}})
        return

    output: list[dict[str, Any]] = []
    if message_open:
        text = "".join(text_parts)
        yield event({
            "type": "response.output_text.done",
            "item_id": message_id,
            "output_index": 0,
            "content_index": 0,
            "text": text,
        })
        message_item = {
            "id": message_id,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
        yield event({"type": "response.output_item.done", "output_index": 0, "item": message_item})
        output.append(message_item)

    for index, state in sorted(tools.items()):
        output_index = len(output)
        call_id = state["id"] or f"call_{uuid.uuid4().hex}"
        item = {
            "id": f"fc_{uuid.uuid4().hex}",
            "type": "function_call",
            "status": "completed",
            "call_id": call_id,
            "name": state["name"],
            "arguments": state["arguments"] or "{}",
        }
        yield event({"type": "response.output_item.added", "output_index": output_index, "item": {**item, "arguments": ""}})
        if state["arguments"]:
            yield event({
                "type": "response.function_call_arguments.delta",
                "item_id": item["id"],
                "output_index": output_index,
                "delta": state["arguments"],
            })
        yield event({
            "type": "response.function_call_arguments.done",
            "item_id": item["id"],
            "output_index": output_index,
            "arguments": item["arguments"],
        })
        yield event({"type": "response.output_item.done", "output_index": output_index, "item": item})
        output.append(item)

    yield event({
        "type": "response.completed",
        "response": {
            "id": response_id,
            "object": "response",
            "status": "completed",
            "model": model,
            "output": output,
        },
    })
