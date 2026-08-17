from __future__ import annotations

import zoneinfo
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.agents import Agent, LLMConnection, Budget, BudgetStatus
from app.agents.services.budget_service import (
    get_period_boundaries,
    get_or_create_status,
    check_budget,
    increment_spent,
    BudgetExceededError,
)


def test_get_period_boundaries():
    # 1. Daily boundary
    # Let's say now is 2026-06-20 15:30:00 in Asia/Kolkata (+05:30)
    # The start of the day in Asia/Kolkata is 2026-06-20 00:00:00 (+05:30) -> which is 2026-06-19 18:30:00 UTC
    # The end of the day is 2026-06-21 00:00:00 (+05:30) -> which is 2026-06-20 18:30:00 UTC
    tz_str = "Asia/Kolkata"
    now_utc = datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc)  # 15:30 Kolkata time
    
    start_utc, end_utc = get_period_boundaries("daily", tz_str, now_utc)
    
    assert start_utc == datetime(2026, 6, 19, 18, 30, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 6, 20, 18, 30, 0, tzinfo=timezone.utc)

    # 2. Monthly boundary
    # Start of month is 2026-06-01 00:00:00 (+05:30) -> 2026-05-31 18:30:00 UTC
    # End of month is 2026-07-01 00:00:00 (+05:30) -> 2026-06-30 18:30:00 UTC
    start_m, end_m = get_period_boundaries("monthly", tz_str, now_utc)
    assert start_m == datetime(2026, 5, 31, 18, 30, 0, tzinfo=timezone.utc)
    assert end_m == datetime(2026, 6, 30, 18, 30, 0, tzinfo=timezone.utc)


def test_get_or_create_status(db_session: Session):
    scope_type = "agent"
    scope_id = "999"
    period = "daily"
    now = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
    tz_str = "Asia/Kolkata"

    # Creation
    status = get_or_create_status(db_session, scope_type, scope_id, period, now, tz_str)
    assert status.id is not None
    assert status.amount_spent == Decimal("0.0000")
    assert status.status == "ok"
    assert status.period_start == datetime(2026, 6, 19, 18, 30, 0, tzinfo=timezone.utc)

    # Retrieval
    status2 = get_or_create_status(db_session, scope_type, scope_id, period, now, tz_str)
    assert status2.id == status.id


def test_budget_policies_and_check(db_session: Session):
    # Setup test agent
    agent = Agent(
        name="Test Budget Agent",
        model="gpt-4",
        max_tokens=2048,
        is_orchestrator=False,
        visibility="shared",
        is_active=True,
        status="active"
    )
    db_session.add(agent)
    db_session.commit()

    # Create budget for agent with "block_new_calls" policy
    budget = Budget(
        scope_type="agent",
        scope_id=str(agent.id),
        period="daily",
        limit_amount=10.0,
        warn_threshold_pct=80,
        on_exceeded="block_new_calls",
        is_active=True
    )
    db_session.add(budget)
    db_session.commit()

    # Check budget is fine under normal conditions
    check_budget(db_session, "agent", str(agent.id))

    # Set spend above threshold but below limit
    now = datetime.now(timezone.utc)
    status = get_or_create_status(db_session, "agent", str(agent.id), "daily", now, "Asia/Kolkata")
    status.amount_spent = Decimal("9.0")
    db_session.commit()

    # Check budget is still fine (no block, though it's near limit)
    check_budget(db_session, "agent", str(agent.id))

    # Set spend to limit
    status.amount_spent = Decimal("10.0")
    db_session.commit()

    # Should raise BudgetExceededError
    with pytest.raises(BudgetExceededError) as exc_info:
        check_budget(db_session, "agent", str(agent.id))
    assert "budget exhausted" in str(exc_info.value)
    
    # The agent status should remain active because the policy is "block_new_calls", not "block_and_pause_agent"
    db_session.refresh(agent)
    assert agent.status == "active"


def test_budget_policy_block_and_pause(db_session: Session):
    agent = Agent(
        name="Pause Agent",
        model="gpt-4",
        max_tokens=2048,
        is_orchestrator=False,
        visibility="shared",
        is_active=True,
        status="active"
    )
    db_session.add(agent)
    db_session.commit()

    budget = Budget(
        scope_type="agent",
        scope_id=str(agent.id),
        period="daily",
        limit_amount=5.0,
        warn_threshold_pct=80,
        on_exceeded="block_and_pause_agent",
        is_active=True
    )
    db_session.add(budget)
    db_session.commit()

    # Set spend to limit
    now = datetime.now(timezone.utc)
    status = get_or_create_status(db_session, "agent", str(agent.id), "daily", now, "Asia/Kolkata")
    status.amount_spent = Decimal("5.5")
    db_session.commit()

    # Should raise and pause the agent
    with pytest.raises(BudgetExceededError):
        check_budget(db_session, "agent", str(agent.id))

    db_session.refresh(agent)
    assert agent.status == "paused"


def test_increment_spent_logic(db_session: Session):
    agent = Agent(
        name="Increment Agent",
        model="gpt-4",
        max_tokens=2048,
        is_orchestrator=False,
        visibility="shared",
        is_active=True,
        status="active"
    )
    db_session.add(agent)
    
    connection = LLMConnection(
        name="Test Cost Connection",
        provider="openai",
        model_name="gpt-4",
        input_cost_per_1k_tokens=Decimal("0.0100"),  # $10 per million -> $0.01 per 1k
        output_cost_per_1k_tokens=Decimal("0.0300"), # $30 per million -> $0.03 per 1k
        cost_currency="USD",
        is_fallback=False
    )
    db_session.add(connection)
    db_session.commit()

    budget = Budget(
        scope_type="agent",
        scope_id=str(agent.id),
        period="daily",
        limit_amount=1.00, # $1.00
        warn_threshold_pct=80,
        on_exceeded="block_new_calls",
        is_active=True
    )
    db_session.add(budget)
    db_session.commit()

    # Call with 10,000 input tokens ($0.10) and 20,000 output tokens ($0.60) -> Total $0.70
    increment_spent(
        db=db_session,
        scope_type="agent",
        scope_id=str(agent.id),
        connection_id=connection.id,
        input_tokens=10000,
        output_tokens=20000
    )

    now = datetime.now(timezone.utc)
    status = get_or_create_status(db_session, "agent", str(agent.id), "daily", now, "Asia/Kolkata")
    assert float(status.amount_spent) == pytest.approx(0.70)
    assert status.status == "ok" # Below 80% ($0.80)

    # Call with 2,000 input tokens ($0.02) and 4,000 output tokens ($0.12) -> Total $0.14 new spend -> Cumulative $0.84
    increment_spent(
        db=db_session,
        scope_type="agent",
        scope_id=str(agent.id),
        connection_id=connection.id,
        input_tokens=2000,
        output_tokens=4000
    )

    db_session.refresh(status)
    assert float(status.amount_spent) == pytest.approx(0.84)
    assert status.status == "warning"
    assert status.warning_fired_at_pct == 80

    # Call with another 10,000 input tokens ($0.10) and 10,000 output tokens ($0.30) -> Total $0.40 -> Cumulative $1.24
    increment_spent(
        db=db_session,
        scope_type="agent",
        scope_id=str(agent.id),
        connection_id=connection.id,
        input_tokens=10000,
        output_tokens=10000
    )

    db_session.refresh(status)
    assert float(status.amount_spent) == pytest.approx(1.24)
    assert status.status == "exceeded"
    assert status.exceeded_fired is True
