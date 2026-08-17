"""Claude Agent sub-package.

Exports ClaudeAgentTool so the tool registry can import from the original
path ``app.agents.services.agent.tools.claude_agent_tool`` via the shim, while
internal code imports from this package directly.
"""

from app.agents.services.agent.tools.claude_agent.claude_agent_tool import ClaudeAgentTool

__all__ = ["ClaudeAgentTool"]
