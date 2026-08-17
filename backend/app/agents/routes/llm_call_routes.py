"""API routes for LLM Call Inspector."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db
from app.dependencies import get_current_user
from app.models.agents import Agent, ChatMessage
from app.agents.models.agents import LlmCallLog
from app.agents.schemas.llm_call import LlmCallLogListItemResponse, LlmCallLogDetailResponse

router = APIRouter(prefix="/api/v1/llm-calls", tags=["LLM Call Inspector"])


@router.get("", response_model=list[LlmCallLogListItemResponse])
def list_llm_call_logs(
    request: Request,
    agent_id: int | None = Query(None),
    session_id: int | None = Query(None),
    model: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(LlmCallLog)
    if workspace_id:
        query = query.filter((LlmCallLog.workspace_id == workspace_id) | (LlmCallLog.workspace_id.is_(None)))
    else:
        query = query.filter(LlmCallLog.workspace_id.is_(None))

    if isinstance(agent_id, int):
        query = query.filter(LlmCallLog.agent_id == agent_id)
    if isinstance(session_id, int):
        query = query.filter(LlmCallLog.session_id == session_id)
    if isinstance(model, str) and model:
        query = query.filter(LlmCallLog.model.ilike(f"%{model}%"))
    if isinstance(start_date, datetime):
        query = query.filter(LlmCallLog.created_at >= start_date)
    if isinstance(end_date, datetime):
        query = query.filter(LlmCallLog.created_at <= end_date)

    logs = query.order_by(LlmCallLog.created_at.desc()).offset(offset).limit(limit).all()

    # Pre-load agents mapping to avoid N+1 queries
    agent_ids = {log.agent_id for log in logs}
    agents_map = {}
    if agent_ids:
        agents = db.query(Agent).filter(Agent.id.in_(agent_ids)).all()
        agents_map = {a.id: a.name for a in agents}

    result = []
    for log in logs:
        # Dynamic summary construction
        summary = "No response content"
        if log.response_text:
            summary = log.response_text
            if len(summary) > 120:
                summary = summary[:120] + "..."
        elif log.response_tool_calls:
            calls = log.response_tool_calls
            tool_names = []
            for tc in calls:
                func_name = tc.get("function", {}).get("name") or tc.get("name")
                if func_name:
                    tool_names.append(func_name)
            if tool_names:
                summary = f"Called tools: {', '.join(tool_names)}"

        result.append(
            LlmCallLogListItemResponse(
                id=log.id,
                agent_id=log.agent_id,
                agent_name=agents_map.get(log.agent_id),
                session_id=log.session_id,
                call_sequence_number=log.call_sequence_number,
                created_at=log.created_at,
                model=log.model,
                input_tokens=log.input_tokens,
                output_tokens=log.output_tokens,
                finish_reason=log.finish_reason,
                summary=summary,
            )
        )
    return result


@router.get("/{call_id}", response_model=LlmCallLogDetailResponse)
def get_llm_call_log_detail(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(LlmCallLog).filter(LlmCallLog.id == call_id)
    if workspace_id:
        query = query.filter((LlmCallLog.workspace_id == workspace_id) | (LlmCallLog.workspace_id.is_(None)))
    else:
        query = query.filter(LlmCallLog.workspace_id.is_(None))
    log = query.first()
    if not log:
        raise HTTPException(status_code=404, detail="LLM call log not found")

    agent = db.query(Agent).filter(Agent.id == log.agent_id).first()
    agent_name = agent.name if agent else None

    # Resolve message history
    resolved_history = []
    history_list = log.message_history or []

    # Handle legacy records that used message_id references
    message_ids = [item.get("message_id") for item in history_list if isinstance(item, dict) and item.get("message_id") is not None]
    messages_map = {}
    if message_ids:
        db_messages = db.query(ChatMessage).filter(ChatMessage.id.in_(message_ids)).all()
        for msg in db_messages:
            messages_map[msg.id] = {
                "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                "content": msg.content,
                "tool_name": msg.tool_name,
                "tool_result": msg.tool_result,
            }

    for item in history_list:
        if not isinstance(item, dict):
            continue
        if "role" in item and ("content" in item or "tool_calls" in item or "tool_call_id" in item or "name" in item):
            resolved_history.append(item)
        elif item.get("message_id") in messages_map:
            resolved_history.append(messages_map[item["message_id"]])
        else:
            resolved_history.append(item)

    return LlmCallLogDetailResponse(
        id=log.id,
        agent_id=log.agent_id,
        agent_name=agent_name,
        session_id=log.session_id,
        call_sequence_number=log.call_sequence_number,
        created_at=log.created_at,
        model=log.model,
        model_params=log.model_params or {},
        system_prompt_base=log.system_prompt_base,
        skills_available=log.skills_available or [],
        skills_injected=log.skills_injected or [],
        memory_injected=log.memory_injected or [],
        message_history=resolved_history,
        tools_available=log.tools_available or [],
        response_text=log.response_text,
        response_tool_calls=log.response_tool_calls or [],
        finish_reason=log.finish_reason,
        input_tokens=log.input_tokens,
        output_tokens=log.output_tokens,
    )
