def _bind():
    import app.ai_gateway.http.mcp.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def call_tool(
    body: MCPToolCallRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Execute an MCP tool call through the governed execution proxy."""
    ws_id = _get_workspace_id(request)
    return await MCPExecutionProxy.execute_tool(
        tool_name=body.tool_name,
        arguments=body.arguments,
        db=db,
        workspace_id=ws_id,
        user_id=None,
        caller_id=body.caller_id,
        server_id=body.server_id,
    )
