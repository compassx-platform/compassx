"""Python Code tool — executes Python in a sandboxed subprocess."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult


class PythonCodeTool(BaseTool):
    key = "python_code"
    name = "Python Code Runner"
    description = (
        "Execute Python code in a sandboxed subprocess. "
        "Available packages: pandas, numpy, matplotlib. "
        "Print results to stdout; they will be returned as output. "
        "WARNING: subprocess isolation only — Docker planned for v2."
    )
    is_async = True
    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
        },
        "required": ["code"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        from app.agents.services.agent.python_sandbox import run_python

        result = run_python(code=args["code"])
        return ToolResult(ok=True, result=result)
