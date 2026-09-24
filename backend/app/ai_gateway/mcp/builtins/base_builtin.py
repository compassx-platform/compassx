"""Base Interface for Built-in Native MCP Servers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.types import MCPTool, MCPToolResult


class BaseBuiltinMCPServer(ABC):
    """Abstract interface for native in-process MCP tools in CompassX."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique server name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @abstractmethod
    def list_tools(self) -> list[MCPTool]:
        """Return list of supported tools and their JSON schemas."""
        pass

    @abstractmethod
    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        db: Session | None = None,
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> MCPToolResult:
        """Execute the tool function and return structured result."""
        pass
