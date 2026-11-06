def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def mcp_server_streamable_post(
    server_name: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """
    Streamable HTTP MCP endpoint (spec 2025-03-26) for a specific MCP server.
    Handles direct JSON-RPC 2.0 requests from Antigravity CLI, Claude Code, and modern MCP clients.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)
    session_id = request.query_params.get("session_id")
    session = mcp_session_manager.get_session(session_id) if session_id else None

    if isinstance(body, list):
        return [
            await process_mcp_jsonrpc_message(
                body=b,
                session=session,
                db=db,
                workspace_id=ws_id,
                user_email=user_email,
                server_filter=server_name,
            )
            for b in body
        ]

    return await process_mcp_jsonrpc_message(
        body=body,
        session=session,
        db=db,
        workspace_id=ws_id,
        user_email=user_email,
        server_filter=server_name,
    )
