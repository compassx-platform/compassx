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

import app.agents.http.budgets.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.budgets.application.list_budgets import list_budgets as list_budgets_action
from app.agents.http.budgets.application.create_budget import create_budget as create_budget_action
from app.agents.http.budgets.application.get_budget_statuses import get_budget_statuses as get_budget_statuses_action
from app.agents.http.budgets.application.update_budget import update_budget as update_budget_action
from app.agents.http.budgets.application.delete_budget import delete_budget as delete_budget_action

logger = logging.getLogger("app.agents.routes.budget_routes")

router = APIRouter(prefix="/api/v1/budgets", tags=["Budgets"])

@router.get("", response_model=List[BudgetResponse])
def list_budgets(
    request: Request,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List all budget configurations with optional scope filtering."""
    return list_budgets_action(request=request, scope_type=scope_type, scope_id=scope_id, db=db, guard=guard)

@router.post("", response_model=BudgetResponse, status_code=201)
def create_budget(
    request: Request,
    body: BudgetCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new budget configuration, validating that the referenced scope exists."""
    return create_budget_action(request=request, body=body, db=db, guard=guard)

@router.get("/status", response_model=List[BudgetStatusResponse])
def get_budget_statuses(
    request: Request,
    scope_type: str,
    scope_id: Optional[str] = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """
    Get the running spend status logs for all active budgets of the given scope.
    Lazily creates status records for the current period if they don't exist.
    """
    return get_budget_statuses_action(request=request, scope_type=scope_type, scope_id=scope_id, db=db, guard=guard)

@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    request: Request,
    budget_id: int,
    body: BudgetUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Update a budget configuration."""
    return update_budget_action(request=request, budget_id=budget_id, body=body, db=db, guard=guard)

@router.delete("/{budget_id}", status_code=204)
def delete_budget(
    request: Request,
    budget_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a budget configuration.

    Removing a cap is the same act as raising one, so it takes the same
    privilege as setting it.
    """
    return delete_budget_action(request=request, budget_id=budget_id, db=db, guard=guard)
