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
