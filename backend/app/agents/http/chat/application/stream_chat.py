def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


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
            try:
                if not body.sandbox:
                    err_msg = ChatMessage(
                        session_id=session_id,
                        role=MessageRole.assistant,
                        content=f"⚠️ **Error**: {str(exc)}",
                        agent_name="System",
                        invocation_depth=0,
                    )
                    bg_db.add(err_msg)
                    bg_db.commit()
                    stream_registry.publish(
                        stream_id,
                        {"type": "done", "session_id": session_id, "message_id": err_msg.id},
                    )
            except Exception as db_err:
                logger.error("Failed to persist error message to chat history: %s", db_err)
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
