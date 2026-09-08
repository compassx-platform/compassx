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

router = APIRouter(prefix="/api/v1/budgets", tags=["Budgets"])
logger = logging.getLogger(__name__)


def _get_budget_or_404(db: Session, budget_id: int, guard: Guard) -> Budget:
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.workspace_id == guard.workspace_id)
        .first()
    )
    if not budget:
        raise HTTPException(404, "Budget configuration not found")
    return budget


@router.get("", response_model=List[BudgetResponse])
def list_budgets(
    request: Request,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List all budget configurations with optional scope filtering."""
    query = db.query(Budget).filter(Budget.workspace_id == guard.workspace_id)

    if scope_type:
        query = query.filter(Budget.scope_type == scope_type)
    if scope_id:
        query = query.filter(Budget.scope_id == scope_id)
    return query.order_by(Budget.created_at.desc()).all()


@router.post("", response_model=BudgetResponse, status_code=201)
def create_budget(
    request: Request,
    body: BudgetCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new budget configuration, validating that the referenced scope exists."""
    guard.require_workspace_admin("Creating a budget")
    workspace_id = guard.workspace_id

    # Validate scope target
    if body.scope_type == "agent":
        try:
            agent_id = int(body.scope_id)
        except ValueError:
            raise HTTPException(400, f"Invalid agent ID format: {body.scope_id}")
        # Resolves in this workspace or 404s. A budget naming an agent from
        # another workspace would silently never apply to anything.
        authorized_agent(db, guard, agent_id, Privilege.BROWSE)

    # Prevent duplicate active budgets for the same scope and period within workspace context
    if body.is_active:
        existing = (
            db.query(Budget)
            .filter(
                Budget.workspace_id == workspace_id,
                Budget.scope_type == body.scope_type,
                Budget.scope_id == body.scope_id,
                Budget.period == body.period,
                Budget.is_active == True,
            )
            .first()
        )
        if existing:
            raise HTTPException(400, f"An active {body.period} budget already exists for {body.scope_type} {body.scope_id}")

    budget = Budget(
        workspace_id=workspace_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        period=body.period,
        limit_amount=body.limit_amount,
        warn_threshold_pct=body.warn_threshold_pct,
        on_exceeded=body.on_exceeded,
        is_active=body.is_active,
        created_by=str(guard.principal.id),
    )
    db.add(budget)
    try:
        db.commit()
        db.refresh(budget)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to save budget configuration: {exc}") from exc
    return budget


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
    workspace_id = guard.workspace_id
    budgets_q = db.query(Budget).filter(
        Budget.workspace_id == workspace_id,
        Budget.scope_type == scope_type,
        Budget.is_active == True,
    )
    if scope_id:
        budgets_q = budgets_q.filter(Budget.scope_id == scope_id)
    budgets = budgets_q.all()

    now = datetime.now(timezone.utc)
    tz_str = get_org_timezone_str(db, workspace_id)
    statuses = []

    for budget in budgets:
        try:
            status = get_or_create_status(db, budget.scope_type, budget.scope_id, budget.period, now, tz_str, workspace_id)
            statuses.append(status)
        except Exception as e:
            logger.error(f"Error resolving budget status for budget ID {budget.id}: {e}")

    # Commit any lazily created statuses
    db.commit()
    return statuses


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    request: Request,
    budget_id: int,
    body: BudgetUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Update a budget configuration."""
    guard.require_workspace_admin("Editing a budget")
    budget = _get_budget_or_404(db, budget_id, guard)

    data = body.model_dump(exclude_none=True)

    # If activating, ensure no duplicate active budget exists for scope and period within workspace context
    if data.get("is_active"):
        existing = (
            db.query(Budget)
            .filter(
                Budget.workspace_id == guard.workspace_id,
                Budget.scope_type == budget.scope_type,
                Budget.scope_id == budget.scope_id,
                Budget.period == budget.period,
                Budget.is_active == True,
                Budget.id != budget.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(400, f"Another active {budget.period} budget already exists for this scope")

    for field, value in data.items():
        setattr(budget, field, value)

    try:
        db.commit()
        db.refresh(budget)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to update budget configuration: {exc}") from exc
    return budget


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
    guard.require_workspace_admin("Deleting a budget")
    budget = _get_budget_or_404(db, budget_id, guard)

    db.delete(budget)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to delete budget configuration: {exc}") from exc
