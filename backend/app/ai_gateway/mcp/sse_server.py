"""Model Context Protocol (MCP) Server-Sent Events (SSE) Engine for CompassX AI Gateway.

Implements the official Model Context Protocol (MCP) 2024-11-05 SSE specification:
1. GET /api/v1/ai-gateway/mcp/sse -> Establishes SSE stream and returns 'endpoint' event.
2. POST /api/v1/ai-gateway/mcp/messages?session_id=... -> Handles JSON-RPC 2.0 requests
   (initialize, tools/list, tools/call, ping) and dispatches responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins import BUILTIN_MCP_SERVERS
from app.ai_gateway.mcp.manager import MCPManager
from app.ai_gateway.mcp.proxy import MCPExecutionProxy
from app.ai_gateway.mcp.types import MCPTool
from app.ai_gateway.models.mcp import MCPServer

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
SESSION_TIMEOUT_SECONDS = 3600  # 1 hour inactivity timeout


class MCPServerSession:
    """Represents an active client SSE connection to the MCP Gateway."""

    def __init__(
        self,
        session_id: str,
        server_filter: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        self.session_id = session_id
        self.server_filter = server_filter
        self.workspace_id = workspace_id
        self.user_email = user_email
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.created_at = time.time()
        self.last_active_at = time.time()
        self.is_active = True

    def touch(self):
        self.last_active_at = time.time()


class MCPSessionManager:
    """In-memory session manager for MCP SSE client connections."""

    def __init__(self):
        self._sessions: Dict[str, MCPServerSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        server_filter: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> MCPServerSession:
        async with self._lock:
            self._cleanup_stale()
            session_id = uuid.uuid4().hex
            session = MCPServerSession(
                session_id=session_id,
                server_filter=server_filter,
                workspace_id=workspace_id,
                user_email=user_email,
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[MCPServerSession]:
        session = self._sessions.get(session_id)
        if session and session.is_active:
            session.touch()
            return session
        return None

    def close_session(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            session.is_active = False

    def _cleanup_stale(self):
        now = time.time()
        stale_ids = [
            sid for sid, s in self._sessions.items()
            if not s.is_active or (now - s.last_active_at) > SESSION_TIMEOUT_SECONDS
        ]
        for sid in stale_ids:
            self._sessions.pop(sid, None)


mcp_session_manager = MCPSessionManager()


async def handle_mcp_sse_stream(
    request: Request,
    server_filter: Optional[str] = None,
    workspace_id: Optional[str] = None,
    user_email: Optional[str] = None,
) -> StreamingResponse:
    """
    Handle GET /mcp/sse or /mcp/servers/{server_name}/sse.
    Emits initial 'endpoint' event with the messages URI and streams downstream events.
    """
    session = await mcp_session_manager.create_session(
        server_filter=server_filter,
        workspace_id=workspace_id,
        user_email=user_email,
    )

    # Base messages endpoint relative to current request path
    messages_endpoint = f"/api/v1/ai-gateway/mcp/messages?session_id={session.session_id}"

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # 1. Send the standard MCP endpoint event
            yield f"event: endpoint\ndata: {messages_endpoint}\n\n"

            # 2. Keep stream open and dispatch messages or keepalive pings
            while session.is_active:
                if await request.is_disconnected():
                    break

                try:
                    # Wait up to 15s for incoming message to stream
                    msg = await asyncio.wait_for(session.queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {msg}\n\n"
                    session.queue.task_done()
                except asyncio.TimeoutError:
                    # Send standard SSE keepalive comment
                    yield ": keep-alive\n\n"

        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            mcp_session_manager.close_session(session.session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


async def process_mcp_jsonrpc_message(
    body: Dict[str, Any],
    session: Optional[MCPServerSession],
    db: Session,
    workspace_id: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process an incoming JSON-RPC 2.0 MCP request and return the JSON-RPC response.
    """
    jsonrpc = body.get("jsonrpc", "2.0")
    msg_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    effective_ws_id = (session.workspace_id if session else None) or workspace_id
    effective_user = (session.user_email if session else None) or user_email or "system"
    server_filter = session.server_filter if session else None

    # Handle Notifications (e.g. notifications/initialized)
    if method == "notifications/initialized":
        return {"jsonrpc": jsonrpc, "result": {}}

    # Handle initialize
    if method == "initialize":
        client_proto = params.get("protocolVersion") or MCP_PROTOCOL_VERSION
        return {
            "jsonrpc": jsonrpc,
            "id": msg_id,
            "result": {
                "protocolVersion": client_proto,
                "capabilities": {
                    "tools": {"listChanged": True},
                    "logging": {},
                },
                "serverInfo": {
                    "name": "compassx-ai-gateway",
                    "version": "1.0.0",
                },
            },
        }

    # Handle ping
    if method == "ping":
        return {
            "jsonrpc": jsonrpc,
            "id": msg_id,
            "result": {},
        }

    # Handle tools/list
    if method == "tools/list":
        tool_defs: list[dict[str, Any]] = []

        # If filtered to a specific server (e.g., compassx_sql_warehouse)
        if server_filter:
            # Check native builtins
            if server_filter in BUILTIN_MCP_SERVERS:
                for t in BUILTIN_MCP_SERVERS[server_filter].list_tools():
                    schema = t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema
                    tool_defs.append({
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": schema or {"type": "object", "properties": {}},
                    })
            else:
                # Query DB server
                db_srv = db.query(MCPServer).filter(
                    MCPServer.name == server_filter,
                    MCPServer.is_enabled == True,  # noqa: E712
                ).first()
                if db_srv:
                    cached = db_srv.cached_tools or []
                    for t in cached:
                        tool_defs.append({
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "inputSchema": t.get("inputSchema") or t.get("input_schema") or {"type": "object", "properties": {}},
                        })
        else:
            # Return all platform tools (built-ins + enabled DB servers)
            all_tools = await MCPManager.list_all_tools_for_workspace(db, effective_ws_id)
            for t in all_tools:
                tool_defs.append({
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.input_schema or {"type": "object", "properties": {}},
                })

        return {
            "jsonrpc": jsonrpc,
            "id": msg_id,
            "result": {
                "tools": tool_defs,
            },
        }

    # Handle tools/call
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        if not tool_name:
            return {
                "jsonrpc": jsonrpc,
                "id": msg_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params: 'name' is required for tools/call",
                },
            }

        try:
            res = await MCPExecutionProxy.execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                db=db,
                workspace_id=effective_ws_id,
                user_id=effective_user,
                caller_id=f"mcp-session-{session.session_id if session else 'stateless'}",
            )

            result_content = []
            if res.result is not None:
                if isinstance(res.result, (dict, list)):
                    result_content.append({"type": "text", "text": json.dumps(res.result, indent=2, default=str)})
                else:
                    result_content.append({"type": "text", "text": str(res.result)})
            elif getattr(res, "error_message", None):
                result_content.append({"type": "text", "text": str(res.error_message)})
            elif getattr(res, "error", None):
                result_content.append({"type": "text", "text": str(res.error)})
            else:
                result_content.append({"type": "text", "text": "Tool executed successfully with no output."})

            is_err = getattr(res, "is_error", False)
            return {
                "jsonrpc": jsonrpc,
                "id": msg_id,
                "result": {
                    "content": result_content,
                    "isError": is_err,
                },
            }
        except Exception as err:
            logger.exception("Error executing MCP tool '%s': %s", tool_name, err)
            return {
                "jsonrpc": jsonrpc,
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool execution failed: {str(err)}"}],
                    "isError": True,
                },
            }

    # Method not found
    return {
        "jsonrpc": jsonrpc,
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not found",
        },
    }
