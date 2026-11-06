"""Live agent stream registry — list, attach, cancel.

A stream is a turn in progress. Attaching to one delivers the same events the
originating client receives: the model's tokens and every tool result as it
arrives. So it discloses exactly what reading the session transcript discloses,
and takes the same ``BROWSE`` on the agent.

``attach_stream`` previously took no workspace and no privilege at all — a
stream id was sufficient to read another workspace's agent output live.
"""

from __future__ import annotations

import asyncio

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_agent

from app.agents.services.stream_registry import stream_registry

from app.database import get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.governance.securable import Securable

def _authorized_stream(stream_id: str, guard: Guard, db: Session, privilege: Privilege):
    """Resolve a stream in the caller's workspace, or 404.

    A stream with no agent is refused rather than allowed: there would be
    nothing to check it against, and an unattributable stream is the one case
    where failing open hands over live agent output.
    """
    with stream_registry._lock:
        stream = stream_registry._streams.get(stream_id)
    if not stream or stream.workspace_id != guard.workspace_id or stream.agent_id is None:
        raise HTTPException(404, "Stream not found")
    authorized_agent(db, guard, stream.agent_id, privilege)
    return stream

import app.agents.http.streams.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.streams.application.list_active_streams import list_active_streams as list_active_streams_action
from app.agents.http.streams.application.attach_stream import attach_stream as attach_stream_action
from app.agents.http.streams.application.cancel_stream import cancel_stream as cancel_stream_action

router = APIRouter(prefix="/api/v1/streams", tags=["Streams"])

@router.get("/active")
def list_active_streams(
    request: Request,
    kind: str | None = Query(default=None, pattern="^agent$"),
    agent_id: int | None = None,
    session_id: int | None = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the running streams the caller may see."""
    return list_active_streams_action(request=request, kind=kind, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.get("/{stream_id}/events")
async def attach_stream(
    stream_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Attach to a running stream and replay its events as SSE."""
    return await attach_stream_action(stream_id=stream_id, db=db, guard=guard)

@router.post("/{stream_id}/cancel")
def cancel_stream(
    request: Request,
    stream_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Stop a running turn.

    EXECUTE, the privilege that started it: whoever may run the agent may stop
    a run of it, and a runaway turn only its starter can kill is worse than one
    stopped by a colleague.
    """
    return cancel_stream_action(request=request, stream_id=stream_id, db=db, guard=guard)
