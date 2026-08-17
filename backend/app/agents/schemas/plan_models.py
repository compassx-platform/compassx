"""Plan Data Models per Part B3 of Spec v2."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class PlanStep(BaseModel):
    id: int
    description: str
    status: StepStatus = StepStatus.PENDING
    verification: str
    result: Optional[Any] = None
    corrections: List[str] = Field(default_factory=list)
    attempts: int = 0
    assets_touched: List[Dict[str, Any]] = Field(default_factory=list)  # D17: assets referenced/modified in this step


class PlanContext(BaseModel):
    landscape_findings: Optional[Any] = None
    conventions: Optional[Any] = None
    uploaded_documents: List[str] = Field(default_factory=list)


class Plan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    session_id: Optional[int] = None
    goal: str
    context: PlanContext = Field(default_factory=PlanContext)
    steps: List[PlanStep] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)
    approved_at: Optional[str] = None
    execution_approved_at: Optional[str] = None
