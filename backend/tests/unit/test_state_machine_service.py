"""Unit tests for workflow state machine service."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.schemas.workflow import WorkflowCreateRequest
from app.services import entity_service, state_machine_service as workflow_service


def _create_default_workflow(entity_name: str) -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        entity_name=entity_name,
        initial_state="OPEN",
        states=["OPEN", "IN_PROGRESS", "RESOLVED"],
        transitions=[
            {"from": "OPEN", "to": "IN_PROGRESS"},
            {"from": "IN_PROGRESS", "to": "RESOLVED"},
        ],
    )


def _make_entity(db: Session, name: str = "work_order"):
    return entity_service.create_entity_definition(
        db,
        definition_data={
            "name": name,
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [
                {"field_name": "title", "field_type": "string", "is_required": True, "is_indexed": False},
                {"field_name": "count", "field_type": "number", "is_required": False, "is_indexed": False},
            ],
            "system_fields": [],
        },
        user_email="test@example.com",
    )


class TestStateMachineService:

    def test_create_or_update_workflow_persists_definition(self, db_session: Session):
        _make_entity(db_session, "invoice")
        workflow = workflow_service.create_or_update_workflow(db_session, _create_default_workflow("invoice"))

        assert workflow.entity_name == "invoice"
        assert workflow.initial_state.upper() == "OPEN"
        assert workflow.is_enabled is True
        assert [state.state_name.upper() for state in workflow.states] == ["OPEN", "IN_PROGRESS", "RESOLVED"]
        assert [
            (transition.from_state.upper(), transition.to_state.upper())
            for transition in workflow.transitions
        ] == [("OPEN", "IN_PROGRESS"), ("IN_PROGRESS", "RESOLVED")]

    def test_create_record_uses_workflow_initial_state(self, db_session: Session):
        _make_entity(db_session, "ticket")
        workflow_service.create_or_update_workflow(db_session, _create_default_workflow("ticket"))

        record = entity_service.create_record(
            db_session,
            entity_name="ticket",
            asset_id=None,
            data={"title": "Fix bug", "count": 1},
            user_email="test@example.com",
        )

        assert record.status.upper() == "OPEN"

    def test_invalid_transition_raises_for_update(self, db_session: Session):
        _make_entity(db_session, "incident")
        workflow_service.create_or_update_workflow(db_session, _create_default_workflow("incident"))
        record = entity_service.create_record(
            db_session,
            entity_name="incident",
            asset_id=None,
            data={"title": "Incident report", "count": 5},
            user_email="test@example.com",
        )

        with pytest.raises(ValueError, match="Invalid transition"):
            entity_service.update_record(
                db_session,
                entity_name="incident",
                record_id=record.id,
                asset_id=None,
                data={},
                status="RESOLVED",
                user_email="test@example.com",
            )

    def test_status_change_allowed_when_no_workflow_exists(self, db_session: Session):
        _make_entity(db_session, "ad_hoc")
        record = entity_service.create_record(
            db_session,
            entity_name="ad_hoc",
            asset_id=None,
            data={"title": "Flexible record", "count": 2},
            user_email="test@example.com",
        )

        updated = entity_service.update_record(
            db_session,
            entity_name="ad_hoc",
            record_id=record.id,
            asset_id=None,
            data={},
            status="PENDING",
            user_email="test@example.com",
        )

        assert updated is not None
        assert updated.status.upper() == "PENDING"
