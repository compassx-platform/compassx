"""Chat session CRUD and SSE streaming endpoint."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_agent, authorized_session
from app.database import SystemSessionLocal as SessionLocal, get_system_db as get_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.models.agents import Agent, ChatMessage, ChatSession
from app.schemas.agents import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ContextUsageResponse,
    SendMessageRequest,
)
from app.agents.services.agent.orchestrator import _resolve_llm_connection, orchestrate_stream
from app.agents.services.agent.compactor import (
    DEFAULT_HIGH_WATERMARK_RATIO,
    DEFAULT_LOW_WATERMARK_K,
    estimate_messages_tokens,
    group_messages_into_turns,
    resolve_model_context_window,
)
from app.agents.services.stream_registry import stream_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/{agent_id}", tags=["Chat"])


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List an agent's chat sessions, with a preview of the last message.

    Sessions belong to the agent rather than to the person who opened them, so
    BROWSE on the agent is what admits someone to the history. That is the
    existing product behaviour — a shared workspace for the agent — made
    explicit rather than changed.
    """
    _get_agent_or_404(db, agent_id, guard, Privilege.BROWSE)
    sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.agent_id == agent_id,
            ChatSession.archived.is_(False),
            ChatSession.workspace_id == guard.workspace_id,
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

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

    has_changes_map: dict[int, bool] = {}
    changes_count_map: dict[int, int] = {}
    try:
        from app.agents.models.agents import ChangeRecord
        change_rows = (
            db.query(
                ChangeRecord.session_id,
                func.count(ChangeRecord.change_id).label("change_count"),
            )
            .filter(ChangeRecord.session_id.in_([str(sid) for sid in session_ids]))
            .group_by(ChangeRecord.session_id)
            .all()
        )
        for row in change_rows:
            try:
                sid = int(row.session_id)
                cnt = int(row.change_count)
                has_changes_map[sid] = cnt > 0
                changes_count_map[sid] = cnt
            except Exception:
                pass
    except Exception:
        pass

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
            has_changes=has_changes_map.get(s.id, False),
            files_changed_count=changes_count_map.get(s.id, 0),
        )
        result.append(res)
    return result


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    request: Request,
    agent_id: int,
    body: ChatSessionCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Open a conversation with an agent.

    EXECUTE, matching ``stream_chat``: a session exists to be run, and a
    principal who may not run the agent has no use for an empty one.
    """
    _get_agent_or_404(db, agent_id, guard, Privilege.EXECUTE)
    session = ChatSession(
        workspace_id=guard.workspace_id, agent_id=agent_id, title=body.title
    )
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
    guard: Guard = Depends(get_guard),
):
    """Archive a session, hiding it from the session list.

    EXECUTE: sessions are shared per agent, so whoever may run the agent may
    tidy up the conversations on it. The history is retained, not deleted.
    """
    session = _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    session.archived = True
    db.commit()


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return a session's transcript.

    Tool output is part of the transcript, so this can contain query results
    the agent read on someone else's behalf — hence a real check rather than
    the bare id lookup that used to be here.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@router.get("/sessions/{session_id}/context", response_model=ContextUsageResponse)
def get_session_context(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Report how much of the model's context window this session is using.

    The response includes the rolling summary, which is a condensation of the
    transcript — so it takes the same privilege as reading the transcript.
    """
    agent = _get_agent_or_404(db, agent_id, guard, Privilege.BROWSE)
    session = _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    llm_conn = _resolve_llm_connection(db, agent)

    context_window = resolve_model_context_window(llm_conn)
    model_name = getattr(llm_conn, "model_name", None) or "Default"

    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    turns = group_messages_into_turns(all_messages)

    candidate_msgs = []
    if session.summary:
        candidate_msgs.append({"role": "system", "content": session.summary})
    for t in turns:
        candidate_msgs.extend(t.to_llm_messages())

    total_tokens = estimate_messages_tokens(candidate_msgs)
    high_watermark = int(context_window * DEFAULT_HIGH_WATERMARK_RATIO)
    usage_percent = round((total_tokens / max(context_window, 1)) * 100, 1)

    return ContextUsageResponse(
        total_tokens=total_tokens,
        context_window=context_window,
        high_watermark=high_watermark,
        usage_percent=min(usage_percent, 100.0),
        total_turns=len(turns),
        retained_turns=min(len(turns), DEFAULT_LOW_WATERMARK_K),
        has_summary=bool(session.summary and session.summary.strip()),
        summary=session.summary,
        summary_updated_at=session.summary_updated_at,
        model_name=model_name,
    )


@router.get("/sessions/{session_id}/plans")
def list_session_plans(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return all stored plans for this session directly from PlanService."""
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    from app.agents.services.agent.plan_service import PlanService
    ps = PlanService()
    plans = ps.get_plans_for_session(session_id)
    return [p.model_dump() for p in plans]


@router.get("/sessions/{session_id}/plans/latest")
def get_latest_session_plan(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return the most recent plan for this session directly from PlanService."""
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    from app.agents.services.agent.plan_service import PlanService
    ps = PlanService()
    plan = ps.get_latest_plan_for_session(session_id)
    return plan.model_dump() if plan else None


@router.post("/sessions/{session_id}/stream")
async def stream_chat(
    request: Request,
    agent_id: int,
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Run a turn of the agent and stream the result.

    EXECUTE is the consequential privilege in this module. A turn runs tools
    under the agent's own service identity, so granting it delegates whatever
    data that identity can reach — it is never inferred from BROWSE.

    The agent's reach is capped by its owner's at resolution time (see
    ``load_agent_permission_set``), so EXECUTE cannot be used to read through
    an agent what the person responsible for it could not read.
    """
    _get_agent_or_404(db, agent_id, guard, Privilege.EXECUTE)
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    workspace_id = guard.workspace_id
    # The identity the turn runs as comes from the resolved principal, not from
    # a token payload field that may be absent — "default_user" was a real
    # fallback, and it is nobody.
    user_id = str(guard.principal.id)

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


def _get_agent_or_404(db: Session, agent_id: int, guard: Guard, privilege: Privilege) -> Agent:
    """Load an agent the caller holds ``privilege`` on.

    The workspace comes from the guard. The previous version fell back to
    ``Agent.workspace_id == None`` when no workspace was resolved, so an
    unscoped request reached the workspace-less agents instead of being
    refused.
    """
    return authorized_agent(db, guard, agent_id, privilege)


def _get_session_or_404(
    db: Session, agent_id: int, session_id: int, guard: Guard, privilege: Privilege
) -> ChatSession:
    """Load a session, having authorised the agent that owns it.

    Sessions carry no grants of their own: a session is a conversation with an
    agent, so the agent is the securable.
    """
    return authorized_session(db, guard, agent_id, session_id, privilege)
