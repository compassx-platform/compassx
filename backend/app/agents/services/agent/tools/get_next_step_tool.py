"""GetNextStep tool implementing Part B6 of Spec v2."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.plan_service import PlanService
from app.models.agents import Agent


class GetNextStepTool(BaseTool):
    @property
    def key(self) -> str:
        return "get_next_step"

    @property
    def description(self) -> str:
        return "Return the first pending step in an active plan, or null if complete."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "Plan ID string"},
            },
            "required": ["plan_id"],
        }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        plan_service = PlanService()
        step = plan_service.get_next_step(args["plan_id"])
        if not step:
            return ToolResult(ok=True, result={"step": None, "completed": True})
        return ToolResult(ok=True, result={"step": step.model_dump(), "completed": False})
