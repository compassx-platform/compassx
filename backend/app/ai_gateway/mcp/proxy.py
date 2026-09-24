"""Governed MCP Tool Execution Proxy with RBAC, 50KB Truncation, and Auditing."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins import BUILTIN_MCP_SERVERS
from app.ai_gateway.mcp.client import MCPClient
from app.ai_gateway.mcp.types import MCPToolResult
from app.ai_gateway.models.inference_log import AIGatewayToolLog
from app.ai_gateway.models.mcp import MCPServer, MCPServerType
from app.ai_gateway.schemas.mcp import MCPToolCallResponse
from app.services.encryption import decrypt_field

logger = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_BYTES = 50 * 1024  # 50KB cap


def _truncate_output(text: str) -> str:
    """Enforce safe output cap (50KB) with explicit truncation marker."""
    if len(text.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
        truncated = text.encode("utf-8")[:MAX_TOOL_OUTPUT_BYTES].decode("utf-8", errors="ignore")
        return f"{truncated}\n\n[TRUNCATED: Output exceeded 50KB safety limit]"
    return text


class MCPExecutionProxy:
    """Executes tools on native or remote MCP servers with governance and audit logging."""

    @staticmethod
    async def execute_tool(
        tool_name: str,
        arguments: dict[str, Any],
        db: Session,
        workspace_id: str | None = None,
        user_id: str | None = None,
        caller_id: str | None = None,
        server_id: int | str | None = None,
    ) -> MCPToolCallResponse:
        start_time = time.time()
        target_server_name = "unknown"
        is_error = False
        error_msg = None
        final_result = None

        # 1. Check if tool belongs to a built-in native server
        for b_name, b_inst in BUILTIN_MCP_SERVERS.items():
            tool_names = [t.name for t in b_inst.list_tools()]
            if tool_name in tool_names:
                target_server_name = b_name
                try:
                    res: MCPToolResult = await asyncio.wait_for(
                        b_inst.call_tool(
                            name=tool_name,
                            arguments=arguments,
                            db=db,
                            workspace_id=workspace_id,
                            user_id=user_id,
                        ),
                        timeout=30.0,
                    )
                    is_error = res.isError
                    # Extract content
                    if res.content:
                        text_contents = [c.text for c in res.content if c.text]
                        final_result = "\n".join(text_contents)
                    else:
                        final_result = ""
                    if is_error:
                        error_msg = final_result
                except asyncio.TimeoutError:
                    is_error = True
                    error_msg = "Tool execution timed out after 30 seconds."
                    final_result = error_msg
                except Exception as e:
                    is_error = True
                    error_msg = f"Native tool runtime error: {str(e)}"
                    final_result = error_msg
                break

        # 2. If not found in built-ins, look up in database registered servers
        if target_server_name == "unknown":
            query = db.query(MCPServer).filter(MCPServer.is_enabled == True)  # noqa: E712
            if server_id is not None:
                s_id_str = str(server_id)
                if s_id_str.isdigit():
                    query = query.filter(MCPServer.id == int(s_id_str))
                elif "." in s_id_str:
                    parts = s_id_str.split(".")
                    if len(parts) == 3:
                        query = query.filter(MCPServer.name == parts[2])
                    elif len(parts) == 2:
                        query = query.filter(MCPServer.name == parts[1])
                else:
                    query = query.filter(MCPServer.name == s_id_str)
            if workspace_id:
                query = query.filter((MCPServer.workspace_id == workspace_id) | (MCPServer.workspace_id.is_(None)))
            servers = query.all()

            matched_server: MCPServer | None = None
            for s in servers:
                cached = s.cached_tools or []
                if any(t.get("name") == tool_name for t in cached):
                    matched_server = s
                    break

            if not matched_server:
                is_error = True
                error_msg = f"Tool '{tool_name}' not found on any active MCP server."
                final_result = error_msg
            else:
                target_server_name = matched_server.name
                server_id = matched_server.id

                auth_headers = {}
                if matched_server.auth_config_enc:
                    try:
                        dec = decrypt_field(matched_server.auth_config_enc)
                        auth_headers = json.loads(dec) if dec else {}
                    except Exception:
                        pass

                env_vars = {}
                if matched_server.env_vars_enc:
                    try:
                        dec = decrypt_field(matched_server.env_vars_enc)
                        env_vars = json.loads(dec) if dec else {}
                    except Exception:
                        pass

                client = MCPClient(
                    endpoint_url=matched_server.endpoint_url,
                    auth_headers=auth_headers,
                    command=matched_server.command,
                    env_vars=env_vars,
                    timeout_s=30.0,
                )

                try:
                    res = await client.call_tool(tool_name, arguments)
                    is_error = res.isError
                    if res.content:
                        text_contents = [c.text for c in res.content if c.text]
                        final_result = "\n".join(text_contents)
                    else:
                        final_result = ""
                    if is_error:
                        error_msg = final_result
                except Exception as e:
                    is_error = True
                    error_msg = f"MCP tool execution failed: {str(e)}"
                    final_result = error_msg

        # 3. Apply safe truncation
        if isinstance(final_result, str):
            final_result = _truncate_output(final_result)

        latency_ms = int((time.time() - start_time) * 1000)

        # 4. Asynchronously log tool audit row to system DB
        try:
            from app.database import SystemSessionLocal
            import uuid as _uuid_lib

            def _to_uuid(val: Any) -> str | None:
                if not val:
                    return None
                try:
                    return str(_uuid_lib.UUID(str(val)))
                except (ValueError, AttributeError, TypeError):
                    return None

            sys_db = SystemSessionLocal()
            try:
                log_entry = AIGatewayToolLog(
                    workspace_id=_to_uuid(workspace_id),
                    user_id=_to_uuid(user_id),
                    caller_id=caller_id,
                    server_id=server_id,
                    server_name=target_server_name,
                    tool_name=tool_name,
                    arguments=arguments,
                    result={"output": final_result} if isinstance(final_result, str) else final_result,
                    is_error="true" if is_error else "false",
                    error_message=error_msg,
                    latency_ms=latency_ms,
                )
                sys_db.add(log_entry)
                sys_db.commit()
            finally:
                sys_db.close()
        except Exception as log_err:
            logger.warning("Could not write tool execution audit log: %s", log_err)

        return MCPToolCallResponse(
            tool_name=tool_name,
            server_name=target_server_name,
            result=final_result,
            is_error=is_error,
            error_message=error_msg,
            latency_ms=latency_ms,
        )
