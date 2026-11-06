def _bind():
    import app.ai_gateway.http.ingress.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI-compatible Chat Completions endpoint with streaming and failover."""
    workspace_id, caller_type, caller_id = _resolve_caller_and_workspace(request)
    effective_user_id = caller_id if caller_type == "dev_agent" else (request.headers.get("X-User-Id") or None)
    effective_caller_id = caller_id or body.user

    if body.stream:
        stream_iter = GatewayService.chat_stream(
            db=db,
            request=body,
            workspace_id=workspace_id,
            user_id=effective_user_id,
            caller_type=caller_type,
            caller_id=effective_caller_id,
        )
        return StreamingResponse(
            _sse_chunk_generator(stream_iter),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            return await GatewayService.chat_complete(
                db=db,
                request=body,
                workspace_id=workspace_id,
                user_id=effective_user_id,
                caller_type=caller_type,
                caller_id=effective_caller_id,
            )
        except ValueError as val_err:
            raise HTTPException(status_code=404, detail=str(val_err))
        except Exception as exc:
            logger.error("Chat completion error: %s", exc)
            raise HTTPException(status_code=502, detail=str(exc))
