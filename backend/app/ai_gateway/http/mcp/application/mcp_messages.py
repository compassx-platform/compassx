def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def mcp_messages(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """
    Standard MCP JSON-RPC 2.0 message handler.
    Dispatches initialize, notifications/initialized, tools/list, tools/call, and ping requests.
    """
    session_id = request.query_params.get("session_id")
    session = mcp_session_manager.get_session(session_id) if session_id else None

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)

    response = await process_mcp_jsonrpc_message(
        body=body,
        session=session,
        db=db,
        workspace_id=ws_id,
        user_email=user_email,
    )

    # If session has an active queue, also put message into queue
    if session and session.is_active and "result" in response:
        try:
            await session.queue.put(json.dumps(response))
        except Exception:
            pass

    return response
