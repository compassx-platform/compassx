"""ClaudeAgentTool — thin orchestrator.

Delegates all heavy lifting to focused modules:
  - code_review_pipeline   : PR diff fetch → LLM review → post comment
  - code_generate_pipeline : git workspace setup → agentic code generation
  - llm_invoker            : LLM communication strategies
  - sub_tool_dispatcher    : tool definitions + dispatch function
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.claude_agent.code_review_pipeline import run_code_review
from app.agents.services.agent.tools.claude_agent.code_generate_pipeline import run_generate_code
from app.agents.services.agent.tools.claude_agent.llm_invoker import ask_claude_text

logger = logging.getLogger(__name__)


class ClaudeAgentTool(BaseTool):
    """Wraps Claude LLM to perform code review and code generation.

    Two actions are supported:
      - ``code_review``  : Review a PR diff and post comments.
      - ``generate_code``: Implement a feature from a natural-language description.
    """

    key = "claude_agent"
    name = "Claude Agent (Code Review & Generation)"
    description = (
        "Use Claude AI to perform code review on a pull request or generate code "
        "from a natural language description. Supports GitHub and Azure DevOps. "
        "Can create PRs, post review comments, and update work items."
    )
    is_async = True
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["code_review", "generate_code"],
                "description": "Task to perform: 'code_review' or 'generate_code'",
            },
            "prompt": {
                "type": "string",
                "description": "Instruction or context for Claude (required for generate_code)",
            },
            "repo": {
                "type": "string",
                "description": "owner/repo (GitHub) or repo name (Azure DevOps)",
            },
            "pr_number": {
                "type": "integer",
                "description": "Pull request number (required for code_review)",
            },
            "provider": {
                "type": "string",
                "enum": ["github", "azure_devops"],
                "default": "github",
                "description": "Git provider",
            },
            "organization": {
                "type": "string",
                "description": "Organization name (required for Azure DevOps)",
            },
            "project": {
                "type": "string",
                "description": "Project name (required for Azure DevOps)",
            },
            "worktree_path": {
                "type": "string",
                "description": "Local path to an existing git worktree (generate_code). "
                               "If omitted, a new worktree is created automatically.",
            },
            "session_id": {
                "type": "string",
                "description": "Claude Code session ID for chaining multi-step calls",
            },
            "workitem_id": {
                "type": "integer",
                "description": "ADO work item ID or GitHub issue number to link/comment on",
            },
        },
        "required": ["action"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        action = args["action"]
        if action == "code_review":
            return run_code_review(args, agent, ask_llm_fn=ask_claude_text)
        if action == "generate_code":
            return run_generate_code(args, agent)
        return ToolResult(ok=False, error=f"Unknown action: '{action}'")
