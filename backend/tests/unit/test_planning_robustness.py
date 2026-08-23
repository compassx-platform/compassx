"""Unit tests for Planning Subsystem Robustness & Hardening."""

from __future__ import annotations

import os
import re
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SystemBase
from app.models.agents import Agent, ChatSession
from app.agents.schemas.plan_models import StepStatus
from app.agents.services.agent.plan_service import PlanService
from app.agents.services.agent.tools.plan_tools import (
    CreatePlanTool,
    GetPlanTool,
    MarkStepTool,
    GetNextStepTool,
    AppendCorrectionTool,
)


@pytest.fixture
def temp_plans_dir(tmp_path):
    return str(tmp_path / "test_plans")


@pytest.fixture
def plan_service(temp_plans_dir):
    return PlanService(storage_dir=temp_plans_dir)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"jobs": None, "ai": None, "auth": None, "catalog": None}},
        poolclass=StaticPool,
    )
    SystemBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    agent = Agent(name="PlanTestAgent")
    session.add(agent)
    session.commit()

    chat_session = ChatSession(agent_id=agent.id, title="Plan Test Session")
    session.add(chat_session)
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_plan_service_cross_platform_storage(plan_service):
    plan = plan_service.create_plan(
        agent_id="1",
        goal="Build analytical pipeline",
        steps=[
            {"description": "Inspect catalog tables", "verification": "Schema verified"},
            {"description": "Create staging notebook", "verification": "Notebook run passed"},
        ],
        session_id=42,
    )

    assert plan.plan_id is not None
    assert len(plan.steps) == 2
    assert plan.steps[0].status == StepStatus.PENDING

    loaded = plan_service.get_plan(plan.plan_id)
    assert loaded is not None
    assert loaded.goal == "Build analytical pipeline"
    assert loaded.session_id == 42


def test_create_plan_tool_session_resolution(db_session, temp_plans_dir, monkeypatch):
    monkeypatch.setattr("app.agents.services.agent.plan_service.DEFAULT_PLANS_DIR", temp_plans_dir)
    agent = db_session.query(Agent).first()
    chat_session = db_session.query(ChatSession).first()

    tool = CreatePlanTool()
    res = tool.execute(
        args={
            "goal": "Build dashboard",
            "steps": [{"description": "Create KPIs", "verification": "Metrics populated"}],
            "context": {"session_id": chat_session.id},
        },
        agent=agent,
        db=db_session,
    )

    assert res.ok is True
    plan_id = res.result["plan_id"]
    assert res.result["session_id"] == chat_session.id

    svc = PlanService(storage_dir=temp_plans_dir)
    p = svc.get_plan(plan_id)
    assert p.session_id == chat_session.id


def test_plan_approval_regex_patterns():
    approval_pattern = re.compile(
        r"^(i\s+)?(approve|approved|proceed|go\s+ahead|yes(,\s*|\s+)approve|looks\s+good|start\s+execution)",
        re.IGNORECASE,
    )

    valid_approvals = [
        "Approved. Proceed to execute the plan.",
        "approved",
        "Approve",
        "I approve",
        "i approve the plan",
        "proceed with execution",
        "Proceed",
        "go ahead and run",
        "yes, approve",
        "Yes approve",
        "looks good to me",
        "start execution now",
    ]
    for phrase in valid_approvals:
        assert approval_pattern.search(phrase.strip()) is not None, f"Failed on valid approval: '{phrase}'"

    invalid_approvals = [
        "What is the status?",
        "No, don't do that",
        "Can you change step 2?",
        "Reject this plan",
    ]
    for phrase in invalid_approvals:
        assert approval_pattern.search(phrase.strip()) is None, f"Incorrectly matched invalid approval: '{phrase}'"


def test_step_lifecycle_transitions(plan_service):
    plan = plan_service.create_plan(
        agent_id="1",
        goal="Test Step Loop",
        steps=[
            {"id": 1, "description": "Step 1", "verification": "Check 1"},
            {"id": 2, "description": "Step 2", "verification": "Check 2"},
        ],
        session_id=99,
    )

    # Initial state
    next_step = plan_service.get_next_step(plan.plan_id)
    assert next_step.id == 1

    # Mark Step 1 in progress then done
    plan_service.mark_step(plan.plan_id, 1, StepStatus.IN_PROGRESS)
    updated = plan_service.get_plan(plan.plan_id)
    assert updated.steps[0].status == StepStatus.IN_PROGRESS
    assert updated.steps[0].attempts == 1

    plan_service.mark_step(plan.plan_id, 1, StepStatus.DONE, result={"output": "created table"})
    updated = plan_service.get_plan(plan.plan_id)
    assert updated.steps[0].status == StepStatus.DONE
    assert updated.steps[0].result == {"output": "created table"}

    # Next step should be Step 2
    next_step = plan_service.get_next_step(plan.plan_id)
    assert next_step.id == 2

    # Append correction note to step 2
    plan_service.append_correction(plan.plan_id, 2, "Adjusted column type to BIGINT")
    updated = plan_service.get_plan(plan.plan_id)
    assert "Adjusted column type to BIGINT" in updated.steps[1].corrections

    # Complete Step 2
    plan_service.mark_step(plan.plan_id, 2, StepStatus.DONE)
    assert plan_service.get_next_step(plan.plan_id) is None


def test_failed_step_blocks_subsequent_steps(plan_service, db_session, temp_plans_dir, monkeypatch):
    monkeypatch.setattr("app.agents.services.agent.plan_service.DEFAULT_PLANS_DIR", temp_plans_dir)
    agent = db_session.query(Agent).first()

    plan = plan_service.create_plan(
        agent_id=str(agent.id),
        goal="Test Failure Blocking",
        steps=[
            {"id": 1, "description": "Step 1 - Create Table", "verification": "Table exists"},
            {"id": 2, "description": "Step 2 - Populate Table", "verification": "Data rows > 0"},
        ],
        session_id=101,
    )

    # Mark Step 1 as FAILED
    plan_service.mark_step(plan.plan_id, 1, StepStatus.FAILED, result={"error": "Schema not found"})

    # get_next_step in plan_service should return None (blocked)
    assert plan_service.get_next_step(plan.plan_id) is None

    # GetNextStepTool should return blocked=True and not return step 2
    tool = GetNextStepTool()
    res = tool.execute(args={"plan_id": plan.plan_id}, agent=agent, db=db_session)
    assert res.ok is True
    assert res.result["blocked"] is True
    assert res.result["completed"] is False
    assert res.result["failed_step_id"] == 1
    assert res.result["step"] is None

