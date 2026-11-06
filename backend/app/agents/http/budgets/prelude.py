"""Budget configuration and running-spend status.

A budget is a spending cap on a workspace or on one agent, and ``on_exceeded``
decides whether crossing it warns or stops the run. That makes writing one an
administrative act: raising a cap spends the organisation's money, and lowering
one halts agents belonging to other people. Budgets are therefore workspace
configuration rather than a securable — there is nothing to grant on them.

Reading is open to members, because a budget status is what tells someone why
their agent stopped mid-run.

Every query is scoped to ``guard.workspace_id``. The previous version fell back
to ``workspace_id == None`` whenever no workspace was resolved, so an unscoped
request read and wrote the workspace-less budgets rather than being refused.
"""

from __future__ import annotations

import logging

from datetime import datetime, timezone

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_agent

from app.database import get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.models.agents import Agent, Budget, BudgetStatus

from app.schemas.agents import BudgetCreate, BudgetResponse, BudgetStatusResponse, BudgetUpdate

from app.agents.services.budget_service import get_or_create_status, get_org_timezone_str

logger = logging.getLogger("app.agents.routes.budget_routes")

def _get_budget_or_404(db: Session, budget_id: int, guard: Guard) -> Budget:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.workspace_id == guard.workspace_id)
        .first()
    )
    if not budget:
        raise HTTPException(404, "Budget configuration not found")
    return budget
