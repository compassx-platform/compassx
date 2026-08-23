"""Chat session CRUD and SSE streaming endpoint."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SystemSessionLocal as SessionLocal, get_system_db as get_db
from app.dependencies import get_current_user
from app.models.agents import Agent, ChatMessage, ChatSession
from app.schemas.agents import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    SendMessageRequest,
)
from app.agents.services.agent.orchestrator import orchestrate_stream
from app.agents.services.stream_registry import stream_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/{agent_id}", tags=["Chat"])


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    _get_agent_or_404(db, agent_id, workspace_id)
    query = db.query(ChatSession).filter(ChatSession.agent_id == agent_id, ChatSession.archived.is_(False))
    if workspace_id:
        query = query.filter(ChatSession.workspace_id == workspace_id)
    else:
        query = query.filter(ChatSession.workspace_id == None)
    sessions = query.order_by(ChatSession.updated_at.desc()).all()

    session_ids = [s.id for s in sessions]
    if not session_ids:
        return []

    from sqlalchemy import func
    subq = (
        db.query(
            ChatMessage.session_id,
            func.max(ChatMessage.id).label("max_id"),
            func.count(ChatMessage.id).label("msg_count"),
        )
        .filter(ChatMessage.session_id.in_(session_ids))
        .group_by(ChatMessage.session_id)
        .all()
    )
    max_id_map = {row.session_id: row.max_id for row in subq}
    count_map = {row.session_id: row.msg_count for row in subq}

    last_msgs: dict[int, str] = {}
    if max_id_map:
        msgs = db.query(ChatMessage).filter(ChatMessage.id.in_(max_id_map.values())).all()
        for m in msgs:
            text = m.content or ""
            if text:
                text = text.replace("\n", " ").strip()
                if len(text) > 90:
                    text = text[:87] + "..."
            last_msgs[m.session_id] = text

    result = []
    for s in sessions:
        res = ChatSessionResponse(
            id=s.id,
            agent_id=s.agent_id,
            title=s.title,
            archived=s.archived,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_message=last_msgs.get(s.id),
            message_count=count_map.get(s.id, 0),
        )
        result.append(res)
    return result


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    request: Request,
    agent_id: int,
    body: ChatSessionCreate,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    _get_agent_or_404(db, agent_id, workspace_id)
    session = ChatSession(workspace_id=workspace_id, agent_id=agent_id, title=body.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
def archive_session(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    session = _get_session_or_404(db, agent_id, session_id, workspace_id)
    session.archived = True
    db.commit()


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    _get_session_or_404(db, agent_id, session_id, workspace_id)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@router.post("/sessions/{session_id}/stream")
async def stream_chat(
    request: Request,
    agent_id: int,
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    _get_agent_or_404(db, agent_id, workspace_id)
    _get_session_or_404(db, agent_id, session_id, workspace_id)
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"

    stream_id = stream_registry.start(
        kind="agent",
        agent_id=agent_id,
        session_id=session_id,
        workspace_id=workspace_id,
        llm_connection_id=body.llm_connection_id,
        detail="Agent stream started",
    )

    async def run_turn():
        bg_db = SessionLocal()
        try:
            async for event in orchestrate_stream(
                session_id=session_id,
                user_content=body.content,
                db=bg_db,
                sandbox=body.sandbox,
                llm_connection_id=body.llm_connection_id,
                context=body.context,
                user_id=user_id,
                workspace_id=workspace_id,
            ):
                stream_registry.touch(
                    stream_id,
                    status="running",
                    detail=f"event:{event.get('type', 'unknown')}",
                )
                stream_registry.publish(stream_id, event)
        except asyncio.CancelledError:
            stream_registry.touch(stream_id, status="cancelled", detail="Agent stream cancelled")
            stream_registry.publish(stream_id, {"type": "error", "message": "Agent stream cancelled"})
            raise
        except Exception as exc:
            logger.exception("Orchestrator error in session %s", session_id)
            stream_registry.touch(stream_id, status="error", detail=str(exc))
            stream_registry.publish(stream_id, {"type": "error", "message": str(exc)})
        finally:
            bg_db.close()
            stream_registry.finish(stream_id)

    task = asyncio.create_task(run_turn())
    stream_registry.set_task(stream_id, task)

    async def event_generator():
        queue = stream_registry.subscribe(stream_id)
        if queue is None:
            return
        try:
            yield f"data: {json.dumps({'type': 'stream_started', 'stream_id': stream_id})}\n\n"
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            logger.info(
                "Client disconnected from agent stream %s for session %s; turn continues in background",
                stream_id,
                session_id,
            )
            raise
        finally:
            stream_registry.unsubscribe(stream_id, queue)
            if task.done():
                with contextlib.suppress(BaseException):
                    task.result()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _get_agent_or_404(db: Session, agent_id: int, workspace_id: str | None = None) -> Agent:
    query = db.query(Agent).filter(Agent.id == agent_id)
    if workspace_id:
        query = query.filter(Agent.workspace_id == workspace_id)
    else:
        query = query.filter(Agent.workspace_id == None)
    agent = query.first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


def _get_session_or_404(db: Session, agent_id: int, session_id: int, workspace_id: str | None = None) -> ChatSession:
    query = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.agent_id == agent_id)
    if workspace_id:
        query = query.filter(ChatSession.workspace_id == workspace_id)
    else:
        query = query.filter(ChatSession.workspace_id == None)
    session = query.first()
    if not session:
        raise HTTPException(404, "Session not found")
    return session
