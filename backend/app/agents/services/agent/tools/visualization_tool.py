"""Visualization tool — pass-through for Vega-Lite chart specs rendered by the frontend."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult


class VisualizationTool(BaseTool):
    key = "visualization"
    name = "Visualization"
    description = (
        "Generate a chart or graph. Provide a Vega-Lite JSON specification. "
        "The frontend will render it inline in the chat. "
        "Use this after running sql_query or python_code to visualize the results."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "spec": {
                "type": "object",
                "description": "A valid Vega-Lite JSON specification object",
            },
        },
        "required": ["spec"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        spec = args.get("spec", {})
        return ToolResult(ok=True, result={"__chart_payload__": spec})
