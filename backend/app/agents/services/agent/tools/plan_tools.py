"""Plan management tools implementing Part B4 of Spec v2."""

from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.plan_service import PlanService
from app.models.agents import Agent


class CreatePlanTool(BaseTool):
    def __init__(self, session_id: int | None = None):
        self.session_id = session_id

    @property
    def key(self) -> str:
        return "create_plan"

    @property
    def description(self) -> str:
        return "Persist a new execution plan after landscape assessment. Returns plan_id."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Original user goal"},
                "steps": {
                    "type": "array",
                    "description": "List of step objects: {id, description, verification}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "description": {"type": "string"},
                            "verification": {"type": "string"},
                        },
                        "required": ["description", "verification"],
                    },
                },
                "context": {"type": "object", "description": "Landscape findings and evidence"},
            },
            "required": ["goal", "steps"],
        }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        plan_service = PlanService()
        plan = plan_service.create_plan(
            agent_id=str(agent.id),
            goal=args["goal"],
            steps=args["steps"],
            context=args.get("context"),
            session_id=self.session_id,
        )
        return ToolResult(
            ok=True,
            result={
                "plan_id": plan.plan_id,
                "status": "created",
                "step_count": len(plan.steps),
                "steps": [s.model_dump() for s in plan.steps],
                "instruction": f"Plan persisted with plan_id='{plan.plan_id}'. When user approves, start by calling get_next_step(plan_id='{plan.plan_id}')."
            }
        )


class GetPlanTool(BaseTool):
    @property
    def key(self) -> str:
        return "get_plan"

    @property
    def description(self) -> str:
        return "Retrieve current plan state by plan_id."

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
        plan = plan_service.get_plan(args["plan_id"])
        if not plan:
            return ToolResult(ok=False, error=f"Plan {args['plan_id']} not found")
        return ToolResult(ok=True, result=plan.model_dump())


class MarkStepTool(BaseTool):
    @property
    def key(self) -> str:
        return "mark_step"

    @property
    def description(self) -> str:
        return "Update a step status in an active plan."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "step_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "done", "failed"]},
                "result": {"type": "object"},
            },
            "required": ["plan_id", "step_id", "status"],
        }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        plan_service = PlanService()
        plan = plan_service.mark_step(
            plan_id=args["plan_id"],
            step_id=args["step_id"],
            status=args["status"],
            result=args.get("result"),
        )
        if not plan:
            return ToolResult(ok=False, error=f"Plan {args['plan_id']} not found")
        return ToolResult(ok=True, result={"plan_id": plan.plan_id, "updated_step": args["step_id"], "status": args["status"]})


class AppendCorrectionTool(BaseTool):
    @property
    def key(self) -> str:
        return "append_correction"

    @property
    def description(self) -> str:
        return "Record a one-line correction note to a step without altering its status."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "step_id": {"type": "integer"},
                "note": {"type": "string"},
            },
            "required": ["plan_id", "step_id", "note"],
        }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        plan_service = PlanService()
        plan = plan_service.append_correction(
            plan_id=args["plan_id"],
            step_id=args["step_id"],
            note=args["note"],
        )
        if not plan:
            return ToolResult(ok=False, error=f"Plan {args['plan_id']} not found")
        return ToolResult(ok=True, result={"plan_id": plan.plan_id, "step_id": args["step_id"], "note_added": args["note"]})


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
