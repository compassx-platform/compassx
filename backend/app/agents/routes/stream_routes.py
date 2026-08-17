from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.agents.services.stream_registry import stream_registry

router = APIRouter(prefix="/api/v1/streams", tags=["Streams"])


@router.get("/active")
def list_active_streams(
    request: Request,
    kind: str | None = Query(default=None, pattern="^agent$"),
    agent_id: int | None = None,
    session_id: int | None = None,
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return {
        "streams": stream_registry.list(kind=kind, agent_id=agent_id, session_id=session_id, workspace_id=workspace_id),
    }


@router.get("/{stream_id}/events")
async def attach_stream(stream_id: str):
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
def cancel_stream(request: Request, stream_id: str):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    # Access registry lock or dictionary to verify workspace boundary
    with stream_registry._lock:
        stream = stream_registry._streams.get(stream_id)
    if not stream or stream.workspace_id != workspace_id:
        raise HTTPException(404, "Stream not found")

    stream_registry.cancel(stream_id)
    return {"ok": True}
