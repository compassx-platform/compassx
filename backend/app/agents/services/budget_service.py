import logging
import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.agents import Agent, LLMConnection, Budget, BudgetStatus

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    def __init__(self, scope_type: str, period: str, limit_amount: float, amount_spent: float, reset_at: datetime):
        self.scope_type = scope_type
        self.period = period
        self.limit_amount = limit_amount
        self.amount_spent = amount_spent
        self.reset_at = reset_at
        super().__init__(
            f"{scope_type.capitalize()} budget exhausted: {amount_spent:.2f} / {limit_amount:.2f} used this {period}. "
            f"Resets at {reset_at.isoformat()}."
        )


def get_org_timezone_str(db: Session, org_id_str: Optional[str]) -> str:
    """Resolve organization timezone, defaulting to 'Asia/Kolkata' if not set."""
    return "Asia/Kolkata"


def get_period_boundaries(period: str, tz_str: str, now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Calculate the UTC start and end times for a daily or monthly calendar period in tz_str timezone."""
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception as e:
        logger.warning(f"Invalid timezone string '{tz_str}', falling back to UTC: {e}")
        tz = zoneinfo.ZoneInfo("UTC")

    if not now:
        now = datetime.now(timezone.utc)

    # Localize current time
    now_tz = now.astimezone(tz)

    if period == "daily":
        start_tz = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        end_tz = start_tz + timedelta(days=1)
    elif period == "monthly":
        start_tz = now_tz.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_tz.month == 12:
            end_tz = start_tz.replace(year=start_tz.year + 1, month=1)
        else:
            end_tz = start_tz.replace(month=start_tz.month + 1)
    else:
        # Fallback default: daily
        start_tz = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        end_tz = start_tz + timedelta(days=1)

    return start_tz.astimezone(timezone.utc), end_tz.astimezone(timezone.utc)


def get_or_create_status(
    db: Session,
    scope_type: str,
    scope_id: str,
    period: str,
    now: datetime,
    tz_str: str,
    workspace_id: Optional[str] = None
) -> BudgetStatus:
    """Lazily load or create the running budget status for the given scope, period, and time."""
    start_utc, end_utc = get_period_boundaries(period, tz_str, now)
    
    query = (
        db.query(BudgetStatus)
        .filter(
            BudgetStatus.scope_type == scope_type,
            BudgetStatus.scope_id == scope_id,
            BudgetStatus.period == period,
            BudgetStatus.period_start == start_utc
        )
    )
    if workspace_id:
        query = query.filter(BudgetStatus.workspace_id == workspace_id)
    else:
        query = query.filter(BudgetStatus.workspace_id == None)
    status = query.first()
    
    if not status:
        status = BudgetStatus(
            workspace_id=workspace_id,
            scope_type=scope_type,
            scope_id=scope_id,
            period=period,
            period_start=start_utc,
            period_end=end_utc,
            amount_spent=Decimal("0.0000"),
            status="ok",
            warning_fired_at_pct=None,
            exceeded_fired=False,
            last_updated_at=now
        )
        db.add(status)
        try:
            db.flush()
        except Exception:
            db.rollback()
            # Try fetching again in case of race condition in concurrent calls
            query = (
                db.query(BudgetStatus)
                .filter(
                    BudgetStatus.scope_type == scope_type,
                    BudgetStatus.scope_id == scope_id,
                    BudgetStatus.period == period,
                    BudgetStatus.period_start == start_utc
                )
            )
            if workspace_id:
                query = query.filter(BudgetStatus.workspace_id == workspace_id)
            else:
                query = query.filter(BudgetStatus.workspace_id == None)
            status = query.first()
            if not status:
                raise
    return status


def check_budget(db: Session, scope_type: str, scope_id: str, workspace_id: Optional[str] = None):
    """
    Check if the active budgets for a scope have been exceeded.
    Raises BudgetExceededError if blocked.
    """
    try:
        query = (
            db.query(Budget)
            .filter(
                Budget.scope_type == scope_type,
                Budget.scope_id == scope_id,
                Budget.is_active == True
            )
        )
        if workspace_id:
            import uuid
            try:
                uuid.UUID(str(workspace_id))
                query = query.filter(Budget.workspace_id == workspace_id)
            except ValueError:
                query = query.filter(Budget.workspace_id == None)
        else:
            query = query.filter(Budget.workspace_id == None)
        budgets = query.all()
    except SQLAlchemyError:
        db.rollback()
        raise
    
    if not budgets:
        return

    now = datetime.now(timezone.utc)
    tz_str = get_org_timezone_str(db, workspace_id)

    for budget in budgets:
        try:
            status = get_or_create_status(db, scope_type, scope_id, budget.period, now, tz_str, workspace_id)
        except SQLAlchemyError:
            db.rollback()
            raise
        limit_val = float(budget.limit_amount)
        spent_val = float(status.amount_spent)
        
        # Enforce if limit is exceeded and action is blocking
        if spent_val >= limit_val:
            if budget.on_exceeded in ("block_new_calls", "block_and_pause_agent"):
                # Automatically pause agent in DB if policy requires it and not already paused
                if scope_type == "agent" and budget.on_exceeded == "block_and_pause_agent":
                    try:
                        agent = db.query(Agent).filter(Agent.id == int(scope_id)).first()
                        if agent and agent.status != "paused":
                            agent.status = "paused"
                            db.commit()
                    except Exception as e:
                        logger.error(f"Failed to auto-pause agent {scope_id} on budget exhaustion: {e}")
                
                raise BudgetExceededError(
                    scope_type=scope_type,
                    period=budget.period,
                    limit_amount=limit_val,
                    amount_spent=spent_val,
                    reset_at=status.period_end
                )


def increment_spent(
    db: Session,
    scope_type: str,
    scope_id: str,
    connection_id: Optional[int],
    input_tokens: int,
    output_tokens: int,
    workspace_id: Optional[str] = None
):
    """Calculate LLM connection cost and increment running budget spent counter atomically."""
    if not connection_id:
        return

    from app.database import AccountSessionLocal
    sys_db = AccountSessionLocal()
    try:
        connection = sys_db.query(LLMConnection).filter(LLMConnection.id == connection_id).first()
        if connection:
            sys_db.expunge(connection)
    finally:
        sys_db.close()
    if not connection:
        logger.warning(f"LLMConnection with ID {connection_id} not found. Skipping cost increment.")
        return

    if connection.input_cost_per_1k_tokens is None or connection.output_cost_per_1k_tokens is None:
        logger.info(f"LLMConnection '{connection.name}' has no cost configured. Skipping cost increment.")
        return

    # Calculate call cost
    input_cost = (input_tokens / 1000.0) * float(connection.input_cost_per_1k_tokens)
    output_cost = (output_tokens / 1000.0) * float(connection.output_cost_per_1k_tokens)
    cost = Decimal(str(input_cost + output_cost))

    if cost <= Decimal("0.0000"):
        return

    # Query active budgets
    query = (
        db.query(Budget)
        .filter(
            Budget.scope_type == scope_type,
            Budget.scope_id == scope_id,
            Budget.is_active == True
        )
    )
    if workspace_id:
        query = query.filter(Budget.workspace_id == workspace_id)
    else:
        query = query.filter(Budget.workspace_id == None)
    budgets = query.all()

    if not budgets:
        return

    now = datetime.now(timezone.utc)
    tz_str = get_org_timezone_str(db, workspace_id)

    for budget in budgets:
        status = get_or_create_status(db, scope_type, scope_id, budget.period, now, tz_str, workspace_id)
        
        # Atomically increment spent
        status.amount_spent = status.amount_spent + cost
        status.last_updated_at = now

        limit_val = float(budget.limit_amount)
        spent_val = float(status.amount_spent)

        # Handle threshold checking
        if spent_val >= limit_val:
            if not status.exceeded_fired:
                status.status = "exceeded"
                status.exceeded_fired = True
                logger.warning(f"Budget exceeded for {scope_type} {scope_id} ({budget.period}): {spent_val:.4f} >= {limit_val:.4f}")
                
                # Auto-pause agent if required
                if scope_type == "agent" and budget.on_exceeded == "block_and_pause_agent":
                    agent = db.query(Agent).filter(Agent.id == int(scope_id)).first()
                    if agent and agent.status != "paused":
                        agent.status = "paused"
                        logger.info(f"Agent {scope_id} paused due to budget policy 'block_and_pause_agent'.")
        else:
            warn_pct = float(budget.warn_threshold_pct or 80)
            if spent_val >= (limit_val * warn_pct / 100.0):
                if status.status == "ok":
                    status.status = "warning"
                    status.warning_fired_at_pct = int(warn_pct)
                    logger.warning(f"Budget warning threshold reached for {scope_type} {scope_id} ({budget.period}): {spent_val:.4f} >= {limit_val * warn_pct / 100.0:.4f}")

    db.commit()
