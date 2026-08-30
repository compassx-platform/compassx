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

router = APIRouter(prefix="/api/v1/streams", tags=["Streams"])


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
    streams = stream_registry.list(
        kind=kind,
        agent_id=agent_id,
        session_id=session_id,
        workspace_id=guard.workspace_id,
    )
    visible = [s for s in streams if s.get("agent_id") is not None]
    return {
        "streams": guard.filter(
            Privilege.BROWSE, visible, lambda s: Securable.agent(str(s["agent_id"]))
        ),
    }


@router.get("/{stream_id}/events")
async def attach_stream(
    stream_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Attach to a running stream and replay its events as SSE."""
    _authorized_stream(stream_id, guard, db, Privilege.BROWSE)

    queue = stream_registry.subscribe(stream_id)
    if queue is None:
        raise HTTPException(404, "Stream not found")

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'stream_attached', 'stream_id': stream_id})}\n\n"
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            stream_registry.unsubscribe(stream_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    _authorized_stream(stream_id, guard, db, Privilege.EXECUTE)
    stream_registry.cancel(stream_id)
    return {"ok": True}
