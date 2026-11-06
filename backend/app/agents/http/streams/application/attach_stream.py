def _bind():
    import app.agents.http.streams.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
