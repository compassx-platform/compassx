"""Dynamic agent tool wrapper for promoted catalog tools."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional
from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.external_tool_executor import execute_agent_tool


class ExternalCatalogTool(BaseTool):
    """Dynamically created BaseTool instance representing a promoted catalog tool."""

    def __init__(
        self,
        tool_id: str,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        pinned_version: Optional[int] = None,
        connection_dependencies: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        agent_type: str = "nova",
        invoked_by: Optional[str] = None,
    ):
        self.tool_id = tool_id
        self.key = name
        self.name = name
        self.description = description or f"External catalog tool: {name}"
        self.input_schema = input_schema or {"type": "object", "properties": {}}
        self.pinned_version = pinned_version
        self.connection_dependencies = connection_dependencies or []
        self.session_id = session_id
        self.agent_type = agent_type
        self.invoked_by = invoked_by
        self.is_async = True

    def execute(
        self,
        args: dict[str, Any],
        agent: Agent,
        db: Session,
    ) -> ToolResult:
        """Execute the external tool via the execution service."""
        # Extract context if present
        context = args.pop("context", {})
        session_id = str(context.get("session_id") or self.session_id or getattr(agent, "id", "session"))
        user_id = str(context.get("user_id") or self.invoked_by or "default_user")

        # Explicit connection_id if provided in args (D5)
        connection_id = args.pop("connection_id", None)
        if not connection_id and self.connection_dependencies:
            connection_id = self.connection_dependencies[0]

        # In async thread or loop
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # We are running inside asyncio loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        execute_agent_tool(
                            tool_id=self.tool_id,
                            version=self.pinned_version,
                            connection_id=connection_id,
                            params=args,
                            session_id=session_id,
                            agent_type=self.agent_type,
                            invoked_by=user_id,
                        ),
                    )
                    res = future.result(timeout=35.0)
            else:
                res = asyncio.run(
                    execute_agent_tool(
                        tool_id=self.tool_id,
                        version=self.pinned_version,
                        connection_id=connection_id,
                        params=args,
                        session_id=session_id,
                        agent_type=self.agent_type,
                        invoked_by=user_id,
                    )
                )
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=f"[runtime_error] Failed to dispatch external tool: {exc}",
            )

        if res.get("ok"):
            return ToolResult(
                ok=True,
                result={
                    "result": res.get("result"),
                    "truncated": res.get("truncated", False),
                },
            )
        else:
            err_type = res.get("error_type", "error")
            err_msg = res.get("message", "Tool execution failed")
            return ToolResult(
                ok=False,
                error=f"[{err_type}] {err_msg}",
            )
