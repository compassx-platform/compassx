from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db
from app.dependencies import get_current_user
from app.models.agents import Agent, Budget, BudgetStatus
from app.schemas.agents import BudgetCreate, BudgetResponse, BudgetStatusResponse, BudgetUpdate
from app.agents.services.budget_service import get_or_create_status, get_org_timezone_str

router = APIRouter(prefix="/api/v1/budgets", tags=["Budgets"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[BudgetResponse])
def list_budgets(
    request: Request,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all budget configurations with optional scope filtering."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(Budget)
    if workspace_id:
        query = query.filter(Budget.workspace_id == workspace_id)
    else:
        query = query.filter(Budget.workspace_id == None)

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
    current_user: dict = Depends(get_current_user)
):
    """Create a new budget configuration, validating that the referenced scope exists."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    # Validate scope target
    if body.scope_type == "agent":
        try:
            agent_id = int(body.scope_id)
            agent_query = db.query(Agent).filter(Agent.id == agent_id)
            if workspace_id:
                agent_query = agent_query.filter(Agent.workspace_id == workspace_id)
            else:
                agent_query = agent_query.filter(Agent.workspace_id == None)
            agent = agent_query.first()
            if not agent:
                raise HTTPException(404, f"Agent with ID {body.scope_id} not found")
        except ValueError:
            raise HTTPException(400, f"Invalid agent ID format: {body.scope_id}")

    # Prevent duplicate active budgets for the same scope and period within workspace context
    if body.is_active:
        dup_query = (
            db.query(Budget)
            .filter(
                Budget.scope_type == body.scope_type,
                Budget.scope_id == body.scope_id,
                Budget.period == body.period,
                Budget.is_active == True
            )
        )
        if workspace_id:
            dup_query = dup_query.filter(Budget.workspace_id == workspace_id)
        else:
            dup_query = dup_query.filter(Budget.workspace_id == None)
        existing = dup_query.first()
        if existing:
            raise HTTPException(400, f"An active {body.period} budget already exists for {body.scope_type} {body.scope_id}")

    username = current_user.get("username") or current_user.get("email") or "system"

    budget = Budget(
        workspace_id=workspace_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        period=body.period,
        limit_amount=body.limit_amount,
        warn_threshold_pct=body.warn_threshold_pct,
        on_exceeded=body.on_exceeded,
        is_active=body.is_active,
        created_by=username
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
    db: Session = Depends(get_db)
):
    """
    Get the running spend status logs for all active budgets of the given scope.
    Lazily creates status records for the current period if they don't exist.
    """
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    # Fetch active budgets first
    query = db.query(Budget).filter(Budget.scope_type == scope_type, Budget.is_active == True)
    if workspace_id:
        query = query.filter(Budget.workspace_id == workspace_id)
    else:
        query = query.filter(Budget.workspace_id == None)

    if scope_id:
        query = query.filter(Budget.scope_id == scope_id)
    budgets = query.all()

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
    db: Session = Depends(get_db)
):
    """Update a budget configuration."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(Budget).filter(Budget.id == budget_id)
    if workspace_id:
        query = query.filter(Budget.workspace_id == workspace_id)
    else:
        query = query.filter(Budget.workspace_id == None)
    budget = query.first()
    if not budget:
        raise HTTPException(404, "Budget configuration not found")

    data = body.model_dump(exclude_none=True)
    
    # If activating, ensure no duplicate active budget exists for scope and period within workspace context
    if data.get("is_active"):
        dup_query = (
            db.query(Budget)
            .filter(
                Budget.scope_type == budget.scope_type,
                Budget.scope_id == budget.scope_id,
                Budget.period == budget.period,
                Budget.is_active == True,
                Budget.id != budget.id
            )
        )
        if workspace_id:
            dup_query = dup_query.filter(Budget.workspace_id == workspace_id)
        else:
            dup_query = dup_query.filter(Budget.workspace_id == None)
        existing = dup_query.first()
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
    db: Session = Depends(get_db)
):
    """Delete a budget configuration."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(Budget).filter(Budget.id == budget_id)
    if workspace_id:
        query = query.filter(Budget.workspace_id == workspace_id)
    else:
        query = query.filter(Budget.workspace_id == None)
    budget = query.first()
    if not budget:
        raise HTTPException(404, "Budget configuration not found")
    
    db.delete(budget)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to delete budget configuration: {exc}") from exc
