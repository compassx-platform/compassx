"""Backward-compatibility shim.

The public import path ``app.agents.services.agent.tools.claude_agent_tool``
is preserved so the tool registry and any external code continue to work
without changes.

All implementation now lives in the ``claude_agent`` sub-package.
"""

from app.agents.services.agent.tools.claude_agent.claude_agent_tool import ClaudeAgentTool

__all__ = ["ClaudeAgentTool"]
