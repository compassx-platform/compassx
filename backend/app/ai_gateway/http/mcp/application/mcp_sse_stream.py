def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def mcp_sse_stream(
    request: Request,
):
    """
    Standard MCP SSE Stream endpoint for the unified CompassX platform.
    Clients connect via HTTP GET and receive the 'endpoint' event with the messages URI.
    """
    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)
    return await handle_mcp_sse_stream(
        request=request,
        server_filter=None,
        workspace_id=ws_id,
        user_email=user_email,
    )
