def _bind():
    import app.ai_gateway.http.ingress.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def responses(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI Responses API used by OpenCode for GPT-5 class models."""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Responses body must be an object.")
    chat_request = _chat_request_from_responses(payload)
    if not chat_request.model:
        raise HTTPException(status_code=400, detail="Model is required.")

    workspace_id, caller_type, caller_id = _resolve_caller_and_workspace(request)
    effective_user_id = caller_id if caller_type == "dev_agent" else (request.headers.get("X-User-Id") or None)
    logger.info("Responses request model=%s stream=%s", chat_request.model, chat_request.stream)

    if chat_request.stream:
        stream_iter = GatewayService.chat_stream(
            db=db,
            request=chat_request,
            workspace_id=workspace_id,
            user_id=effective_user_id,
            caller_type=caller_type,
            caller_id=caller_id,
        )
        return StreamingResponse(
            _responses_event_stream(stream_iter, chat_request.model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        completed = await GatewayService.chat_complete(
            db=db,
            request=chat_request,
            workspace_id=workspace_id,
            user_id=effective_user_id,
            caller_type=caller_type,
            caller_id=caller_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Responses completion error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    message = completed.choices[0].message if completed.choices else None
    output: list[dict[str, Any]] = []
    if message and message.content:
        output.append({
            "id": "msg_complete",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": message.content, "annotations": []}],
        })
    for call in (message.tool_calls if message and message.tool_calls else []):
        output.append({
            "id": call.id,
            "type": "function_call",
            "status": "completed",
            "call_id": call.id,
            "name": call.function.name,
            "arguments": call.function.arguments,
        })
    return {
        "id": completed.id,
        "object": "response",
        "status": "completed",
        "model": completed.model,
        "output": output,
    }
