"""Plan management tools implementing Part B4 of Spec v2."""

from __future__ import annotations

import logging
from typing import Any, Dict
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.plan_service import PlanService
from app.agents.schemas.plan_models import StepStatus
from app.models.agents import Agent

logger = logging.getLogger(__name__)


class CreatePlanTool(BaseTool):
    def __init__(self, session_id: int | None = None):
        self.session_id = session_id

    @property
    def key(self) -> str:
        return "create_plan"

    @property
    def name(self) -> str:
        return "Create Plan"

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
        session_id = (
            args.get("session_id")
            or (args.get("context") if isinstance(args.get("context"), dict) else {}).get("session_id")
            or self.session_id
        )
        if session_id is not None:
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                session_id = None

        plan = plan_service.create_plan(
            agent_id=str(agent.id),
            goal=args["goal"],
            steps=args["steps"],
            context=args.get("context"),
            session_id=session_id,
        )
        return ToolResult(
            ok=True,
            result={
                "plan_id": plan.plan_id,
                "session_id": plan.session_id,
                "status": "created",
                "step_count": len(plan.steps),
                "steps": [s.model_dump() for s in plan.steps],
                "instruction": f"Plan persisted with plan_id='{plan.plan_id}'. When user approves, start by calling get_next_step(plan_id='{plan.plan_id}').",
            },
        )


class GetPlanTool(BaseTool):
    @property
    def key(self) -> str:
        return "get_plan"

    @property
    def name(self) -> str:
        return "Get Plan"

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
        plan_id = str(args.get("plan_id") or "").strip()
        if not plan_id:
            return ToolResult(ok=False, error="plan_id is required")
        plan = plan_service.get_plan(plan_id)
        if not plan:
            return ToolResult(ok=False, error=f"Plan {plan_id} not found")
        return ToolResult(ok=True, result=plan.model_dump())


class MarkStepTool(BaseTool):
    @property
    def key(self) -> str:
        return "mark_step"

    @property
    def name(self) -> str:
        return "Mark Step"

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
        plan_id = str(args.get("plan_id") or "").strip()
        step_id = args.get("step_id")
        status_val = args.get("status")

        if not plan_id or step_id is None or not status_val:
            return ToolResult(ok=False, error="plan_id, step_id, and status are required")

        try:
            step_id_int = int(step_id)
        except (ValueError, TypeError):
            return ToolResult(ok=False, error=f"Invalid step_id: {step_id}")

        plan = plan_service.mark_step(
            plan_id=plan_id,
            step_id=step_id_int,
            status=status_val,
            result=args.get("result"),
        )
        if not plan:
            return ToolResult(ok=False, error=f"Plan {plan_id} not found")
        return ToolResult(
            ok=True,
            result={"plan_id": plan.plan_id, "updated_step": step_id_int, "status": status_val},
        )


class AppendCorrectionTool(BaseTool):
    @property
    def key(self) -> str:
        return "append_correction"

    @property
    def name(self) -> str:
        return "Append Correction"

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
        plan_id = str(args.get("plan_id") or "").strip()
        step_id = args.get("step_id")
        note = args.get("note")

        if not plan_id or step_id is None or not note:
            return ToolResult(ok=False, error="plan_id, step_id, and note are required")

        try:
            step_id_int = int(step_id)
        except (ValueError, TypeError):
            return ToolResult(ok=False, error=f"Invalid step_id: {step_id}")

        plan = plan_service.append_correction(
            plan_id=plan_id,
            step_id=step_id_int,
            note=note,
        )
        if not plan:
            return ToolResult(ok=False, error=f"Plan {plan_id} not found")
        return ToolResult(
            ok=True,
            result={"plan_id": plan.plan_id, "step_id": step_id_int, "note_added": note},
        )


class GetNextStepTool(BaseTool):
    @property
    def key(self) -> str:
        return "get_next_step"

    @property
    def name(self) -> str:
        return "Get Next Step"

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
        plan_id = str(args.get("plan_id") or "").strip()
        if not plan_id:
            return ToolResult(ok=False, error="plan_id is required")
        plan = plan_service.get_plan(plan_id)
        if not plan:
            return ToolResult(ok=False, error=f"Plan {plan_id} not found")

        # Check if plan is blocked by a failed step
        for s in plan.steps:
            if s.status == StepStatus.FAILED:
                return ToolResult(
                    ok=True,
                    result={
                        "step": None,
                        "completed": False,
                        "blocked": True,
                        "failed_step_id": s.id,
                        "failed_step_desc": s.description,
                        "message": f"Execution blocked: Step {s.id} failed. You must retry or correct Step {s.id} using append_correction and mark_step(step_id={s.id}, status='in_progress'|'done') before proceeding.",
                    },
                )

        step = plan_service.get_next_step(plan_id)
        if not step:
            return ToolResult(ok=True, result={"step": None, "completed": True, "blocked": False})
        return ToolResult(ok=True, result={"step": step.model_dump(), "completed": False, "blocked": False})
