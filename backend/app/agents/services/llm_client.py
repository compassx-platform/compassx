"""Unified async LLM client factory.

Given an LLMConnection row, returns an async client that exposes a
common interface for streaming chat completions.

Supported providers: openai, anthropic, azure, gemini, ollama,
compatible, litellm. Bedrock and Vertex are stubbed with a clear error
until boto3 / google-cloud-aiplatform are added to requirements.txt.

Tool/function-calling contract
-------------------------------
Pass tools as OpenAI-style tool definitions:
    [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]

The `chat_stream()` method yields either:
    {"type": "text", "delta": str}
    {"type": "tool_use", "tool_calls": [{"name": str, "arguments": dict, "id": str}]}
    {"type": "done", "usage": {"input_tokens": int, "output_tokens": int}}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from typing import AsyncIterator

from app.models.agents import LLMConnection, LLMProvider
from app.services.encryption import decrypt_field

logger = logging.getLogger(__name__)

_background_tasks = set()

OPENAI_IMPORT_ERROR = "openai package not installed. Run: pip install openai"


def _openai_http_client():
    """Create an HTTP client that ignores ambient proxy environment variables."""
    try:
        import httpx
    except ImportError:
        return None
    return httpx.AsyncClient(trust_env=False)


def _uses_max_completion_tokens(model_name: str | None) -> bool:
    return (model_name or "").lower().startswith("gpt-5")


async def chat_stream(
    conn: LLMConnection,
    messages: list[dict],
    tools: list[dict] | None = None,
    system_prompt: str | None = None,
    agent_id: int | None = None,
    session_id: int | None = None,
    workspace_id: str | None = None,
) -> AsyncIterator[dict]:
    """Stream a chat completion.

    Args:
        conn: LLMConnection ORM row (with api_key_enc already loaded).
        messages: OpenAI-style message list [{"role": ..., "content": ...}].
        tools: Optional list of tool definitions (OpenAI format).
        system_prompt: If provided, prepended as system message.
        agent_id: Optional Agent ID for logging telemetry.
        session_id: Optional Session ID for logging telemetry.
        workspace_id: Optional Workspace/Org ID for budget tracking.

    Yields dicts: {"type": "text"|"tool_use"|"done", ...}
    """
    logger.debug(
        "Chat stream called with agent_id=%s, session_id=%s, connection=%s, provider=%s",
        agent_id,
        session_id,
        getattr(conn, "name", None),
        getattr(conn, "provider", None),
    )

    if agent_id is not None:
        from app.database import SystemSessionLocal as SessionLocal
        from app.agents.services.budget_service import check_budget, BudgetExceededError
        db = SessionLocal()
        try:
            check_budget(db, "agent", str(agent_id), workspace_id)
        except BudgetExceededError as e:
            raise e
        finally:
            db.close()

    clean_messages = _clean_messages_for_llm(messages)

    response_text = ""
    response_tool_calls = []
    input_tokens = None
    output_tokens = None
    finish_reason = None

    async def _stream_wrapper() -> AsyncIterator[dict]:
        nonlocal response_text, response_tool_calls, input_tokens, output_tokens, finish_reason
        match conn.provider:
            case LLMProvider.openai | LLMProvider.ollama | LLMProvider.compatible:
                stream_gen = _openai_stream(conn, clean_messages, tools, system_prompt)
            case LLMProvider.anthropic:
                stream_gen = _anthropic_stream(conn, clean_messages, tools, system_prompt)
            case LLMProvider.azure:
                stream_gen = _azure_stream(conn, clean_messages, tools, system_prompt)
            case LLMProvider.gemini:
                stream_gen = _gemini_stream(conn, clean_messages, tools, system_prompt)
            case LLMProvider.litellm:
                stream_gen = _litellm_stream(conn, clean_messages, tools, system_prompt)
            case LLMProvider.bedrock | LLMProvider.vertex:
                raise NotImplementedError(
                    f"Provider '{conn.provider}' is not yet implemented. "
                    "Install boto3 (Bedrock) or google-cloud-aiplatform (Vertex) and extend llm_client.py."
                )
            case _:
                raise ValueError(f"Unknown LLM provider: {conn.provider}")

        async for chunk in stream_gen:
            if chunk["type"] == "text":
                response_text += chunk.get("delta", "")
            elif chunk["type"] == "tool_use":
                response_tool_calls.extend(chunk.get("tool_calls", []))
            elif chunk["type"] == "done":
                usage = chunk.get("usage") or {}
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                finish_reason = chunk.get("finish_reason")
            yield chunk

    try:
        async for chunk in _stream_wrapper():
            yield chunk
    finally:
        if agent_id is not None:
            try:
                connection_id = getattr(conn, "id", None)
                # Snapshot messages at the exact time of call to prevent subsequent loop mutations from polluting this log
                snapshot_messages = [dict(m) for m in messages]
                task = asyncio.create_task(
                    save_llm_call_log(
                        connection_id=connection_id,
                        messages=snapshot_messages,
                        tools=tools,
                        system_prompt=system_prompt,
                        agent_id=agent_id,
                        session_id=session_id,
                        response_text=response_text,
                        response_tool_calls=response_tool_calls,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        finish_reason=finish_reason,
                        conn=conn if connection_id is None else None,
                        workspace_id=workspace_id,
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
            except Exception as e:
                logger.warning("Failed to schedule LLM call logging: %s", e)


def _clean_messages_for_llm(messages: list[dict]) -> list[dict]:
    allowed_keys = {"role", "content", "name", "tool_call_id", "tool_calls"}
    cleaned = []
    for msg in messages:
        cloned = {k: v for k, v in msg.items() if k in allowed_keys}
        cleaned.append(cloned)
    return cleaned


async def save_llm_call_log(
    connection_id: int | None,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
    agent_id: int | None,
    session_id: int | None,
    response_text: str | None,
    response_tool_calls: list[dict],
    input_tokens: int | None,
    output_tokens: int | None,
    finish_reason: str | None,
    conn: LLMConnection | None = None,
    workspace_id: str | None = None,
):
    from app.database import SystemSessionLocal as SessionLocal, AccountSessionLocal
    from app.agents.models.agents import LlmCallLog, AgentSkillAttachment
    from sqlalchemy import func

    if conn is None and connection_id is not None:
        acc_db = AccountSessionLocal()
        try:
            conn = acc_db.query(LLMConnection).filter(LLMConnection.id == connection_id).first()
        finally:
            acc_db.close()

    if conn is None:
        logger.warning("No LLMConnection found for ID %s", connection_id)
        return

    db = SessionLocal()
    try:
        if workspace_id is None and session_id is not None:
            from app.models.agents import ChatSession
            session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session_obj and session_obj.workspace_id:
                workspace_id = session_obj.workspace_id

        if workspace_id is None and agent_id is not None:
            from app.models.agents import Agent
            agent_obj = db.query(Agent).filter(Agent.id == agent_id).first()
            if agent_obj and agent_obj.workspace_id:
                workspace_id = agent_obj.workspace_id

        # 1. Available skills
        skills_available = []
        attachments = (
            db.query(AgentSkillAttachment)
            .filter(AgentSkillAttachment.agent_id == agent_id)
            .order_by(AgentSkillAttachment.position)
            .all()
        )
        for att in attachments:
            if att.skill:
                skills_available.append({
                    "skill_id": att.skill.id,
                    "name": att.skill.name,
                    "description": att.skill.description,
                    "position": att.position,
                })

        # 2. Extract injected skills from message history
        skills_injected = []

        tool_call_to_name = {}
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tc_id = tc.get("id")
                    tc_name = tc.get("function", {}).get("name") or tc.get("name")
                    if tc_id and tc_name:
                        tool_call_to_name[tc_id] = tc_name

        for msg in messages:
            if msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id")
                tool_name = tool_call_to_name.get(tc_id)
                if tool_name == "read_skill":
                    content = msg.get("content")
                    if content:
                        try:
                            data = json.loads(content) if isinstance(content, str) else content
                            if isinstance(data, dict) and "body" in data:
                                skills_injected.append({
                                    "name": data.get("name"),
                                    "description": data.get("description"),
                                    "body": data.get("body"),
                                    "version": data.get("version"),
                                })
                        except Exception:
                            pass

        # 3. Message history (payload sent to LLM with base64 truncated for logging)
        message_history = []
        for msg in messages:
            item = {}
            for k in ("role", "content", "tool_calls", "tool_call_id", "name"):
                if k in msg and msg[k] is not None:
                    val = msg[k]
                    if k == "content" and isinstance(val, list):
                        sanitized_list = []
                        for part in val:
                            if isinstance(part, dict) and part.get("type") == "image_url":
                                url = part.get("image_url", {}).get("url", "")
                                if len(url) > 100:
                                    sanitized_list.append({
                                        "type": "image_url",
                                        "image_url": {"url": url[:60] + "... [base64 image truncated for log]"}
                                    })
                                else:
                                    sanitized_list.append(part)
                            else:
                                sanitized_list.append(part)
                        val = sanitized_list
                    item[k] = val
            message_history.append(item)

        # 4. Tools available (full definitions sent to LLM)
        tools_available = tools or []

        # 5. Call sequence number
        seq = db.query(func.count(LlmCallLog.id)).filter(
            LlmCallLog.agent_id == agent_id,
            LlmCallLog.session_id == session_id
        ).scalar() or 0
        call_sequence_number = seq + 1

        # 6. Model params
        model_params = {
            "max_tokens": conn.max_tokens,
            "timeout_s": conn.timeout_s,
            "is_fallback": conn.is_fallback,
        }

        valid_ws_id = None
        if workspace_id:
            import uuid
            try:
                uuid.UUID(str(workspace_id))
                valid_ws_id = str(workspace_id)
            except ValueError:
                valid_ws_id = None

        # 7. Create log
        call_log = LlmCallLog(
            workspace_id=valid_ws_id,
            agent_id=agent_id,
            session_id=session_id,
            call_sequence_number=call_sequence_number,
            model=conn.model_name,
            model_params=model_params,
            system_prompt_base=system_prompt,
            skills_available=skills_available,
            skills_injected=skills_injected,
            message_history=message_history,
            tools_available=tools_available,
            response_text=response_text or None,
            response_tool_calls=response_tool_calls,
            finish_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(call_log)
        db.commit()

        # Increment budget spent asynchronously
        if input_tokens is not None and output_tokens is not None and agent_id is not None:
            try:
                from app.agents.services.budget_service import increment_spent
                increment_spent(
                    db=db,
                    scope_type="agent",
                    scope_id=str(agent_id),
                    connection_id=connection_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    workspace_id=workspace_id,
                )
            except Exception as e:
                logger.error(f"Failed to increment budget spent: {e}")
    except Exception as e:
        logger.exception("Failed to write LLM Call Log to database (failing open): %s", e)
    finally:
        db.close()



async def ping(conn: LLMConnection) -> tuple[bool, str]:
    """Send a minimal completion request to verify connectivity.

    Returns (True, "") on success, or (False, error_message) on failure.
    """
    try:
        messages = [{"role": "user", "content": "ping"}]
        async for chunk in chat_stream(conn, messages):
            if chunk["type"] in ("text", "done"):
                break
        return True, ""
    except Exception as exc:
        logger.warning("LLM ping failed for connection %s: %s", conn.id, exc)
        return False, str(exc)


# ── Provider implementations ─────────────────────────────────────────────────

async def _openai_stream(
    conn: LLMConnection,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
) -> AsyncIterator[dict]:
    try:
        import openai
    except ImportError:
        raise RuntimeError(OPENAI_IMPORT_ERROR)

    api_key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else "ollama"
    base_url = conn.base_url or None

    http_client = _openai_http_client()
    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=conn.timeout_s, http_client=http_client)
    try:
        async for chunk in _openai_stream_with_client(client, conn, messages, tools, system_prompt):
            yield chunk
    finally:
        await client.close()


def _convert_messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-style messages to Anthropic message format.

    Anthropic rules:
    - Messages must strictly alternate between 'user' and 'assistant'.
    - Tool use: assistant content = [{"type": "tool_use", "id": ..., "name": ..., "input": {...}}]
    - Tool result: MUST be in the next user turn as [{"type": "tool_result", "tool_use_id": ..., "content": ...}]
    - A user turn can contain BOTH tool_result blocks AND text blocks (merged into one list).
    - Consecutive same-role messages are merged.
    """
    import json as _json

    # Step 1: Convert each message to an Anthropic-style (role, content_blocks) pair
    converted: list[tuple[str, list]] = []

    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role", "user")

        if role == "assistant" and msg.get("tool_calls"):
            # Assistant turn with tool calls
            blocks = []
            text_content = msg.get("content") or ""
            if text_content:
                blocks.append({"type": "text", "text": text_content})
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                try:
                    parsed_args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    parsed_args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", tc.get("name", "")),
                    "input": parsed_args,
                })
            converted.append(("assistant", blocks))

        elif role == "tool":
            # Collect all consecutive tool result messages → one user turn
            tool_blocks = []
            while i < len(messages) and messages[i].get("role") == "tool":
                t = messages[i]
                tool_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": t.get("tool_call_id", ""),
                    "content": t.get("content", ""),
                })
                i += 1
            converted.append(("user", tool_blocks))
            continue  # i already advanced

        elif role == "assistant":
            text = msg.get("content") or ""
            converted.append(("assistant", [{"type": "text", "text": text}] if text else [{"type": "text", "text": ""}]))

        else:  # user
            raw_content = msg.get("content") or ""
            if isinstance(raw_content, list):
                blocks = []
                for item in raw_content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            blocks.append({"type": "text", "text": item.get("text", "")})
                        elif item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                try:
                                    header, b64_data = url.split(";base64,", 1)
                                    media_type = header.replace("data:", "") or "image/png"
                                    blocks.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": b64_data,
                                        },
                                    })
                                except Exception:
                                    pass
                        elif item.get("type") == "image":
                            blocks.append(item)
                    elif isinstance(item, str):
                        blocks.append({"type": "text", "text": item})
                converted.append(("user", blocks if blocks else [{"type": "text", "text": ""}]))
            else:
                text = raw_content if isinstance(raw_content, str) else str(raw_content)
                converted.append(("user", [{"type": "text", "text": text}]))

        i += 1

    # Step 2: Merge consecutive same-role turns (Anthropic requires strict alternation)
    merged: list[tuple[str, list]] = []
    for role, blocks in converted:
        if merged and merged[-1][0] == role:
            # Merge blocks into the previous same-role turn
            merged[-1][1].extend(blocks)
        else:
            merged.append([role, list(blocks)])

    # Step 3: Serialize to final Anthropic format
    result = []
    for role, blocks in merged:
        # Simplify: if a user turn has only one text block, use string content
        if role == "user" and len(blocks) == 1 and blocks[0].get("type") == "text":
            result.append({"role": "user", "content": blocks[0]["text"]})
        elif role == "assistant" and len(blocks) == 1 and blocks[0].get("type") == "text":
            result.append({"role": "assistant", "content": blocks[0]["text"]})
        else:
            result.append({"role": role, "content": blocks})

    return result


async def _anthropic_stream(
    conn: LLMConnection,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
) -> AsyncIterator[dict]:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = decrypt_field(conn.api_key_enc)
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=conn.timeout_s)

    # Convert OpenAI-style tools to Anthropic format
    anthropic_tools = None
    if tools:
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]

    kwargs: dict = {
        "model": conn.model_name,
        "messages": _convert_messages_to_anthropic(messages),
        "max_tokens": conn.max_tokens,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if anthropic_tools:
        kwargs["tools"] = anthropic_tools

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            event_type = getattr(event, "type", None)

            if event_type == "content_block_delta":
                delta = event.delta
                if getattr(delta, "type", None) == "text_delta":
                    yield {"type": "text", "delta": delta.text}

            elif event_type == "content_block_stop":
                block = getattr(event, "content_block", None)
                if block and getattr(block, "type", None) == "tool_use":
                    yield {
                        "type": "tool_use",
                        "tool_calls": [{
                            "id": block.id,
                            "name": block.name,
                            "arguments": block.input,
                        }],
                    }

            elif event_type == "message_stop":
                msg = await stream.get_final_message()
                yield {
                    "type": "done",
                    "usage": {
                        "input_tokens": msg.usage.input_tokens,
                        "output_tokens": msg.usage.output_tokens,
                    },
                }


async def _azure_stream(
    conn: LLMConnection,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
) -> AsyncIterator[dict]:
    try:
        import openai
    except ImportError:
        raise RuntimeError(OPENAI_IMPORT_ERROR)

    cfg = conn.config or {}
    api_key = decrypt_field(conn.api_key_enc)
    http_client = _openai_http_client()
    client = openai.AsyncAzureOpenAI(
        api_key=api_key,
        azure_endpoint=conn.base_url or "",
        api_version=cfg.get("api_version", "2024-02-01"),
        timeout=conn.timeout_s,
        http_client=http_client,
    )
    # Reuse OpenAI streaming logic with the Azure client
    # by temporarily swapping the client reference
    conn_copy = type("_C", (), {
        "api_key_enc": None,
        "base_url": None,
        "model_name": cfg.get("deployment_name", conn.model_name),
        "max_tokens": conn.max_tokens,
        "timeout_s": conn.timeout_s,
        "provider": LLMProvider.azure,
    })()

    # Delegate to openai stream with already-constructed client
    try:
        async for chunk in _openai_stream_with_client(client, conn_copy, messages, tools, system_prompt):
            yield chunk
    finally:
        await client.close()


async def _openai_stream_with_client(
    client,
    conn,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
) -> AsyncIterator[dict]:
    """Internal helper — same as _openai_stream but accepts a pre-built client."""
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    kwargs: dict = {
        "model": conn.model_name,
        "messages": all_messages,
        "stream": True,
    }
    if getattr(conn, "provider", None) in (LLMProvider.openai, LLMProvider.azure, LLMProvider.litellm):
        kwargs["stream_options"] = {"include_usage": True}

    if _uses_max_completion_tokens(conn.model_name):
        kwargs["max_completion_tokens"] = conn.max_tokens
    else:
        kwargs["max_tokens"] = conn.max_tokens
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    tool_calls_buffer: dict[int, dict] = {}
    last_chunk = None

    stream = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            stream = await client.chat.completions.create(**kwargs)
            break
        except Exception as exc:
            is_conn_error = "Connection" in type(exc).__name__ or "connect" in str(exc).lower() or "socket" in str(exc).lower()
            if is_conn_error and attempt < max_retries - 1:
                import asyncio
                backoff = 1.0 * (2 ** attempt)
                logger.warning(
                    "LLM stream creation connection error (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, max_retries, backoff, exc
                )
                await asyncio.sleep(backoff)
            else:
                raise

    if not stream:
        raise RuntimeError("Failed to establish LLM completion stream")

    async for chunk in stream:
        last_chunk = chunk
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue
        delta = choice.delta

        if delta.content:
            yield {"type": "text", "delta": delta.content}

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_buffer:
                    tool_calls_buffer[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                if tc.function:
                    if tc.function.name:
                        tool_calls_buffer[idx]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tc.function.arguments

        if choice.finish_reason in ("tool_calls", "stop") and tool_calls_buffer:
            parsed = []
            for tc in tool_calls_buffer.values():
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {"raw": tc["arguments"]}
                parsed.append({"id": tc["id"], "name": tc["name"], "arguments": args})
            yield {"type": "tool_use", "tool_calls": parsed}
            tool_calls_buffer.clear()

    usage = getattr(last_chunk, "usage", None) if last_chunk else None
    yield {
        "type": "done",
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        } if usage else {},
    }


async def _litellm_stream(
    conn: LLMConnection,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
) -> AsyncIterator[dict]:
    """Stream via LiteLLM — routes to 100+ providers using the model string prefix.

    Model string format (same as LiteLLM docs):
        "gpt-4o"                      → OpenAI
        "anthropic/claude-opus-4-6"   → Anthropic via LiteLLM
        "bedrock/anthropic.claude-…"  → AWS Bedrock
        "vertex_ai/gemini-pro"        → Google Vertex
        "ollama/llama3"               → local Ollama
        etc.

    The connection's api_key is passed as the provider API key.
    Set base_url to point at a self-hosted LiteLLM proxy if needed.
    Extra provider-specific params go in conn.config (e.g. {"aws_region_name": "us-east-1"}).
    """
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm package not installed. Run: pip install litellm")

    api_key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else None
    cfg = conn.config or {}

    all_messages: list[dict] = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    kwargs: dict = {
        "model": conn.model_name,
        "messages": all_messages,
        "max_tokens": conn.max_tokens,
        "stream": True,
        **cfg,  # forward extra provider params (aws_region_name, vertex_project, etc.)
    }
    if api_key:
        kwargs["api_key"] = api_key
    if conn.base_url:
        kwargs["api_base"] = conn.base_url  # litellm uses api_base, not base_url
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    tool_calls_buffer: dict[int, dict] = {}
    last_chunk = None

    # When a proxy base_url is set, local litellm detects the claude model name and
    # sends an Anthropic-format request to the proxy. The proxy's litellm then
    # converts Anthropic tools to Databricks format and strips "type":"object" from
    # input_schema. Bypass local litellm entirely and call the proxy directly via
    # the OpenAI SDK — the proxy's OpenAI→Databricks path preserves the schema.
    if conn.base_url:
        try:
            import openai as _openai
        except ImportError:
            raise RuntimeError(OPENAI_IMPORT_ERROR)

        http_client = _openai_http_client()
        proxy_client = _openai.AsyncOpenAI(
            api_key=api_key or "litellm",
            base_url=conn.base_url,
            timeout=conn.timeout_s,
            http_client=http_client,
        )
        try:
            async for event in _openai_stream_with_client(proxy_client, conn, messages, tools, system_prompt):
                yield event
        finally:
            await proxy_client.close()
        return

    response = await litellm.acompletion(**kwargs)
    async for chunk in response:
        last_chunk = chunk
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue
        delta = choice.delta

        if getattr(delta, "content", None):
            yield {"type": "text", "delta": delta.content}

        if getattr(delta, "tool_calls", None):
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_buffer:
                    tool_calls_buffer[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                if tc.function:
                    if tc.function.name:
                        tool_calls_buffer[idx]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tc.function.arguments

        if getattr(choice, "finish_reason", None) in ("tool_calls", "stop") and tool_calls_buffer:
            parsed = []
            for tc in tool_calls_buffer.values():
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {"raw": tc["arguments"]}
                parsed.append({"id": tc["id"], "name": tc["name"], "arguments": args})
            yield {"type": "tool_use", "tool_calls": parsed}
            tool_calls_buffer.clear()

    usage = getattr(last_chunk, "usage", None) if last_chunk else None
    yield {
        "type": "done",
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        } if usage else {},
    }


async def _gemini_stream(
    conn: LLMConnection,
    messages: list[dict],
    tools: list[dict] | None,
    system_prompt: str | None,
) -> AsyncIterator[dict]:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai package not installed. Run: pip install google-genai")

    api_key = decrypt_field(conn.api_key_enc)
    client = genai.Client(api_key=api_key)

    gemini_contents = _build_gemini_contents(messages, types)
    gemini_tools = _build_gemini_tools(tools, types)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=conn.max_tokens,
        tools=gemini_tools or None,
    )

    response = await client.aio.models.generate_content(
        model=conn.model_name,
        contents=gemini_contents,
        config=config,
    )

    parts = []
    if getattr(response, "candidates", None):
        candidate = response.candidates[0]
        parts = getattr(getattr(candidate, "content", None), "parts", None) or []

    tool_calls = []
    for index, part in enumerate(parts):
        if getattr(part, "text", None):
            yield {"type": "text", "delta": part.text}

        function_call = getattr(part, "function_call", None)
        if function_call:
            tool_call = {
                "id": getattr(function_call, "id", None) or f"gemini_tool_{index}",
                "name": function_call.name,
                "arguments": _coerce_mapping(getattr(function_call, "args", None)),
            }
            thought_signature = getattr(part, "thought_signature", None)
            if thought_signature:
                tool_call["thought_signature"] = thought_signature
            tool_calls.append(tool_call)

    if tool_calls:
        yield {"type": "tool_use", "tool_calls": tool_calls}

    yield {
        "type": "done",
        "usage": _gemini_usage(response),
    }


def _build_gemini_tools(tools: list[dict] | None, types_module) -> list[Any]:
    if not tools:
        return []

    declarations = []
    for tool in tools:
        function = tool.get("function", {})
        declarations.append(
            types_module.FunctionDeclaration(
                name=function.get("name", "tool"),
                description=function.get("description", ""),
                parameters=_sanitize_gemini_schema(function.get("parameters", {"type": "object", "properties": {}})),
            )
        )

    return [types_module.Tool(function_declarations=declarations)]


def _sanitize_gemini_schema(schema: Any) -> Any:
    """Return a Gemini-compatible subset of JSON Schema.

    Gemini's function declaration schema rejects OpenAPI/JSON Schema fields such
    as ``additionalProperties`` after the SDK converts them to
    ``additional_properties``. Keep the structure useful for the model while
    removing unsupported keywords recursively.
    """
    if isinstance(schema, list):
        return [_sanitize_gemini_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    unsupported = {
        "additionalProperties",
        "additional_properties",
        "$schema",
        "$id",
        "unevaluatedProperties",
        "patternProperties",
        "propertyNames",
    }
    sanitized: dict[str, Any] = {}
    for key, value in schema.items():
        if key in unsupported:
            continue
        sanitized[key] = _sanitize_gemini_schema(value)
    return sanitized


def _build_gemini_contents(messages: list[dict], types_module) -> list[Any]:
    contents = []
    tool_call_names: dict[str, str] = {}

    for message in messages:
        role = message.get("role")
        if role == "system":
            continue

        if role == "assistant" and message.get("tool_calls"):
            parts = _build_gemini_assistant_tool_parts(message["tool_calls"], tool_call_names, types_module)
            if parts:
                contents.append(types_module.Content(role="model", parts=parts))
            continue

        if role == "tool":
            contents.append(_build_gemini_tool_content(message, tool_call_names, types_module))
            continue

        text_content = _build_gemini_text_content(message, types_module)
        if text_content is not None:
            contents.append(text_content)

    return contents


def _coerce_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [_extract_message_text_part(item) for item in content]
        return "\n".join(part for part in text_parts if part)
    if content is None:
        return ""
    return json.dumps(content)


def _build_gemini_assistant_tool_parts(tool_calls: list[dict], tool_call_names: dict[str, str], types_module) -> list[Any]:
    parts = []
    for tool_call in tool_calls:
        function = tool_call.get("function", {})
        call_id = tool_call.get("id") or ""
        function_name = function.get("name", "tool")
        thought_signature = (
            tool_call.get("thought_signature")
            or tool_call.get("extra_content", {}).get("google", {}).get("thought_signature")
        )
        if call_id:
            tool_call_names[call_id] = function_name
        function_call = types_module.FunctionCall(
            id=call_id or None,
            name=function_name,
            args=_coerce_mapping(_parse_json_string(function.get("arguments"))),
        )
        parts.append(_build_gemini_function_call_part(function_call, thought_signature, types_module))
    return parts


def _build_gemini_function_call_part(function_call: Any, thought_signature: Any, types_module) -> Any:
    part_kwargs = _part_keyword_args(types_module, function_call)
    if thought_signature:
        part_kwargs.update(_part_signature_kwargs(types_module, thought_signature))
    return types_module.Part(**part_kwargs)


def _part_keyword_args(types_module, function_call: Any) -> dict[str, Any]:
    if hasattr(types_module.Part, "model_fields"):
        return {"functionCall": function_call}
    return {"function_call": function_call}


def _part_signature_kwargs(types_module, thought_signature: Any) -> dict[str, Any]:
    if hasattr(types_module.Part, "model_fields"):
        return {"thoughtSignature": thought_signature}
    return {"thought_signature": thought_signature}


def _build_gemini_tool_content(message: dict, tool_call_names: dict[str, str], types_module) -> Any:
    tool_call_id = message.get("tool_call_id") or ""
    tool_name = tool_call_names.get(tool_call_id, "tool")
    response_payload = _build_gemini_tool_response(message.get("content"))
    return types_module.Content(
        role="tool",
        parts=[
            types_module.Part.from_function_response(
                name=tool_name,
                response=response_payload,
            )
        ],
    )


def _build_gemini_text_content(message: dict, types_module) -> Any | None:
    content_val = message.get("content")
    role = "model" if message.get("role") == "assistant" else "user"
    if isinstance(content_val, list):
        import base64 as _b64
        parts = []
        for item in content_val:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    t = item.get("text", "")
                    if t:
                        parts.append(types_module.Part.from_text(text=t))
                elif item.get("type") == "image_url":
                    url = item.get("image_url", {}).get("url", "")
                    if url.startswith("data:"):
                        try:
                            header, b64_data = url.split(";base64,", 1)
                            media_type = header.replace("data:", "") or "image/png"
                            raw_bytes = _b64.b64decode(b64_data)
                            parts.append(types_module.Part.from_bytes(data=raw_bytes, mime_type=media_type))
                        except Exception as b64_err:
                            logger.warning("Failed to decode image_url for Gemini: %s", b64_err)
            elif isinstance(item, str):
                parts.append(types_module.Part.from_text(text=item))
        if not parts:
            return None
        return types_module.Content(role=role, parts=parts)

    text = _coerce_message_text(content_val)
    if not text:
        return None
    return types_module.Content(
        role=role,
        parts=[types_module.Part.from_text(text=text)],
    )


def _extract_message_text_part(item: Any) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    if item.get("type") == "text" and item.get("text"):
        return str(item["text"])
    if "text" in item and item["text"]:
        return str(item["text"])
    return ""


def _parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return {"value": value}


def _build_gemini_tool_response(content: Any) -> dict[str, Any]:
    parsed = _parse_json_string(content)
    if isinstance(parsed, dict):
        return parsed
    return {"result": parsed}


def _gemini_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return {}
    return {
        "input_tokens": getattr(usage, "prompt_token_count", 0),
        "output_tokens": getattr(usage, "response_token_count", getattr(usage, "candidates_token_count", 0)),
    }
