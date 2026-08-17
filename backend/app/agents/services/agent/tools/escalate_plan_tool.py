"""Escalate-to-Plan Tool (Part B2 of Spec v5).

Converts an in-flight single_action into a tracked multi-stage plan when the
scope turns out to be larger than originally classified.  Only auto-injected
when agent_manifest.capabilities.planning.enabled is True.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.plan_service import PlanService
from app.models.agents import Agent


class EscalateToPlanTool(BaseTool):

    def __init__(self, session_id: int | None = None):
        self.session_id = session_id

    @property
    def key(self) -> str:
        return "escalate_to_plan"

    @property
    def description(self) -> str:
        return (
            "Escalate the current task from a single-action to a tracked multi-stage plan. "
            "Call this when you discover mid-task that the scope is larger than a single step. "
            "Provide a reason explaining why escalation is needed, plus the goal and steps for the new plan."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why this task needs to be escalated to a multi-stage plan.",
                },
                "goal": {
                    "type": "string",
                    "description": "The original human goal (verbatim).",
                },
                "steps": {
                    "type": "array",
                    "description": "Ordered list of plan steps.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "verification": {"type": "string"},
                        },
                        "required": ["description", "verification"],
                    },
                },
            },
            "required": ["reason", "goal", "steps"],
        }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        reason = args.get("reason", "")
        goal = args.get("goal", "")
        steps = args.get("steps", [])

        if not goal or not steps:
            return ToolResult(
                ok=False,
                error="goal and steps are required to escalate to a plan.",
            )

        plan_svc = PlanService()
        plan = plan_svc.create_plan(
            agent_id=str(agent.id),
            goal=goal,
            steps=steps,
            context={"landscape_findings": f"Escalated from single_action: {reason}"},
            session_id=self.session_id,
        )
        return ToolResult(
            ok=True,
            result={
                "plan_id": plan.plan_id,
                "goal": plan.goal,
                "step_count": len(plan.steps),
                "escalation_reason": reason,
                "message": (
                    f"Task escalated to a multi-stage plan ({len(plan.steps)} steps). "
                    "Present this plan to the human for approval before executing any writes."
                ),
            },
        )
