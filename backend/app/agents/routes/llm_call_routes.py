"""API routes for LLM Call Inspector.

A call log is the whole of one model call: the system prompt, the message
history, the tools offered, and the response. That is the transcript of an
agent run in its rawest form, so it is governed by the agent — ``BROWSE``, the
same privilege as reading the session it came from.

The list endpoint filters rather than refusing, so a caller sees the calls made
by the agents they may browse and nothing else. It previously returned every
log in the workspace, plus every log with a null workspace, to anyone.
"""

from __future__ import annotations

from datetime import datetime

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_agent

from app.database import get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.governance.securable import Securable

from app.models.agents import Agent, ChatMessage

from app.agents.models.agents import LlmCallLog

from app.agents.schemas.llm_call import LlmCallLogListItemResponse, LlmCallLogDetailResponse

import app.agents.http.llm_calls.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.llm_calls.application.list_llm_call_logs import list_llm_call_logs as list_llm_call_logs_action
from app.agents.http.llm_calls.application.get_llm_call_log_detail import get_llm_call_log_detail as get_llm_call_log_detail_action

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
    guard: Guard = Depends(get_guard),
):
    return list_llm_call_logs_action(request=request, agent_id=agent_id, session_id=session_id, model=model, start_date=start_date, end_date=end_date, limit=limit, offset=offset, db=db, guard=guard)

@router.get("/{call_id}", response_model=LlmCallLogDetailResponse)
def get_llm_call_log_detail(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return one call in full: prompt, history, tools, and response."""
    return get_llm_call_log_detail_action(request=request, call_id=call_id, db=db, guard=guard)
