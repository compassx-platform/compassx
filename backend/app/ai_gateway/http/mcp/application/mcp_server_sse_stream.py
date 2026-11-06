def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def mcp_server_sse_stream(
    server_name: str,
    request: Request,
):
    """
    Standard MCP SSE Stream endpoint for a specific MCP server (built-in native or proxied).
    """
    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)
    return await handle_mcp_sse_stream(
        request=request,
        server_filter=server_name,
        workspace_id=ws_id,
        user_email=user_email,
    )
