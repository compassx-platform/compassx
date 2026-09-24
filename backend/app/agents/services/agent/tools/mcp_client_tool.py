"""Dynamic BaseTool wrapper for External MCP Server tools."""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.ai_gateway.mcp.proxy import MCPExecutionProxy


class ExternalMCPTool(BaseTool):
    """Dynamically created BaseTool instance representing an external MCP tool."""

    def __init__(
        self,
        server_id: int | str,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
        session_id: Optional[str] = None,
        invoked_by: Optional[str] = None,
    ):
        self.server_id = server_id
        self.server_name = server_name
        self.key = tool_name
        self.name = tool_name
        self.description = description or f"External MCP tool from {server_name}: {tool_name}"
        self.input_schema = input_schema or {"type": "object", "properties": {}}
        self.session_id = session_id
        self.invoked_by = invoked_by
        self.is_async = True

    def execute(
        self,
        args: dict[str, Any],
        agent: Agent,
        db: Session,
    ) -> ToolResult:
        """Execute the MCP tool via the MCPExecutionProxy."""
        from app.database import AccountSessionLocal

        sys_db = None
        if AccountSessionLocal is not None:
            sys_db = AccountSessionLocal()
        else:
            sys_db = db

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        MCPExecutionProxy.execute_tool(
                            tool_name=self.name,
                            arguments=args,
                            db=sys_db,
                            server_id=self.server_id,
                            caller_id=f"agent-{getattr(agent, 'id', 'unknown')}",
                            user_id=self.invoked_by,
                        ),
                    )
                    res = future.result(timeout=40.0)
            else:
                res = asyncio.run(
                    MCPExecutionProxy.execute_tool(
                        tool_name=self.name,
                        arguments=args,
                        db=sys_db,
                        server_id=self.server_id,
                        caller_id=f"agent-{getattr(agent, 'id', 'unknown')}",
                        user_id=self.invoked_by,
                    )
                )

            if not res.is_error:
                return ToolResult(
                    ok=True,
                    result={"output": res.result, "server": self.server_name, "latency_ms": res.latency_ms},
                )
            else:
                return ToolResult(
                    ok=False,
                    error=res.error_message or f"MCP tool '{self.name}' execution failed.",
                )
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=f"[mcp_runtime_error] Failed executing MCP tool '{self.name}': {exc}",
            )
        finally:
            if sys_db is not None and sys_db is not db:
                sys_db.close()
