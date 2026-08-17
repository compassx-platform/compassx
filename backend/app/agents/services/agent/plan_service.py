"""Plan Storage and Service tools implementing Part B4, B8, and B9."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional
import uuid

from app.agents.schemas.plan_models import Plan, PlanContext, PlanStep, StepStatus


class PlanService:
    """Manages creation, storage, state updates, and retrieval of Plan objects."""

    def __init__(self, storage_dir: str = "/tmp/compassx_plans"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_plan_path(self, plan_id: str) -> str:
        return os.path.join(self.storage_dir, f"plan_{plan_id}.json")

    def create_plan(
        self,
        agent_id: str,
        goal: str,
        steps: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        plan_id: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> Plan:
        ctx = PlanContext(**context) if context else PlanContext()
        plan_steps = [
            PlanStep(
                id=idx + 1 if "id" not in step else step["id"],
                description=step["description"],
                verification=step.get("verification", "Verification check passed"),
                status=StepStatus(step.get("status", "pending")),
            )
            for idx, step in enumerate(steps)
        ]

        plan = Plan(
            plan_id=plan_id or str(uuid.uuid4()),
            agent_id=agent_id,
            session_id=session_id,
            goal=goal,
            context=ctx,
            steps=plan_steps,
        )
        self.save_plan(plan)
        return plan

    def save_plan(self, plan: Plan) -> None:
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        filepath = self._get_plan_path(plan.plan_id)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(plan.model_dump_json(indent=2))

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        filepath = self._get_plan_path(plan_id)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Plan.model_validate(data)

    def get_active_plan_for_session(self, session_id: int) -> Optional[Plan]:
        """Scan plan storage for an active (approved & in-progress/pending steps remaining) plan for session_id."""
        if not os.path.exists(self.storage_dir):
            return None
        for filename in os.listdir(self.storage_dir):
            if filename.startswith("plan_") and filename.endswith(".json"):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        plan = Plan.model_validate(data)
                        if plan.session_id == session_id:
                            # Check if plan is approved and has pending or in_progress steps
                            has_incomplete_steps = any(
                                step.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS)
                                for step in plan.steps
                            )
                            if plan.approved_at and has_incomplete_steps:
                                return plan
                except Exception:
                    continue
        return None

    def get_next_step(self, plan_id: str) -> Optional[PlanStep]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        for step in plan.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def mark_step(
        self,
        plan_id: str,
        step_id: int,
        status: StepStatus,
        result: Optional[Any] = None,
    ) -> Optional[Plan]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None

        for step in plan.steps:
            if step.id == step_id:
                step.status = status
                if result is not None:
                    step.result = result
                if status == StepStatus.IN_PROGRESS:
                    step.attempts += 1
                break

        self.save_plan(plan)
        return plan

    def append_correction(self, plan_id: str, step_id: int, note: str) -> Optional[Plan]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None

        for step in plan.steps:
            if step.id == step_id:
                step.corrections.append(note)
                break

        self.save_plan(plan)
        return plan

    def approve_plan(self, plan_id: str) -> Optional[Plan]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        plan.approved_at = datetime.now(timezone.utc).isoformat()
        self.save_plan(plan)
        return plan

    def approve_execution(self, plan_id: str) -> Optional[Plan]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        plan.execution_approved_at = datetime.now(timezone.utc).isoformat()
        self.save_plan(plan)
        return plan
