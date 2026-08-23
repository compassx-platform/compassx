"""Plan Storage and Service tools implementing Part B4, B8, and B9."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional
import uuid

from app.agents.schemas.plan_models import Plan, PlanContext, PlanStep, StepStatus

logger = logging.getLogger(__name__)

DEFAULT_PLANS_DIR = os.environ.get(
    "COMPASSX_PLANS_DIR",
    os.path.join(tempfile.gettempdir(), "compassx_plans"),
)


class PlanService:
    """Manages creation, storage, state updates, and retrieval of Plan objects."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or DEFAULT_PLANS_DIR
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
                description=step.get("description") or step.get("text") or f"Step {idx + 1}",
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
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Plan.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to load plan %s: %s", plan_id, exc)
            return None

    def get_plans_for_session(self, session_id: int) -> List[Plan]:
        """Return all plans created for a given session, ordered newest first."""
        if not os.path.exists(self.storage_dir):
            return []
        plans: List[Plan] = []
        for filename in os.listdir(self.storage_dir):
            if filename.startswith("plan_") and filename.endswith(".json"):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        p = Plan.model_validate(data)
                        if p.session_id == session_id:
                            plans.append(p)
                except Exception:
                    continue
        plans.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
        return plans

    def get_latest_plan_for_session(self, session_id: int) -> Optional[Plan]:
        """Return the most recently created or updated plan for a session."""
        plans = self.get_plans_for_session(session_id)
        return plans[0] if plans else None

    def get_active_plan_for_session(self, session_id: int) -> Optional[Plan]:
        """Return the latest active (approved & incomplete steps remaining) plan for session_id."""
        plans = self.get_plans_for_session(session_id)
        for plan in plans:
            has_incomplete_steps = any(
                step.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS)
                for step in plan.steps
            )
            if plan.approved_at and has_incomplete_steps:
                return plan
        return None

    def get_next_step(self, plan_id: str) -> Optional[PlanStep]:
        plan = self.get_plan(plan_id)
        if not plan:
            return None
        for step in plan.steps:
            if step.status == StepStatus.FAILED:
                # Execution is blocked on failed step
                return None
            if step.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
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

        found = False
        for step in plan.steps:
            if step.id == step_id:
                step.status = status
                if result is not None:
                    step.result = result
                if status == StepStatus.IN_PROGRESS:
                    step.attempts += 1
                found = True
                break

        if not found:
            logger.warning("Step %s not found in plan %s", step_id, plan_id)

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
