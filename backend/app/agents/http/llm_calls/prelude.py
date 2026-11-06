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
