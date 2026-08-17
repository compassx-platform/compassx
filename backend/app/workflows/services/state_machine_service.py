from datetime import datetime, timezone
import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.entity import EntityRecord
from app.models.workflow import (
    EntityState,
    EntityStateLog,
    EntityTransition,
    EntityWorkflow,
)
from app.schemas.workflow import WorkflowCreateRequest, WorkflowTransition

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_state(value: str) -> str:
    return value.strip().lower()


def _ensure_unique_states(states: list[str]) -> list[str]:
    cleaned = [_normalize_state(state) for state in states if state.strip()]
    if len(cleaned) != len(set(cleaned)):
        raise ValueError("Workflow states must be unique.")
    if not cleaned:
        raise ValueError("Workflow must define at least one state.")
    return cleaned


def _validate_transitions(states: set[str], transitions: Iterable[WorkflowTransition]) -> list[WorkflowTransition]:
    validated: list[WorkflowTransition] = []
    for transition in transitions:
        from_state = _normalize_state(transition.from_state)
        to_state = _normalize_state(transition.to_state)
        if from_state not in states:
            raise ValueError(f"Transition from '{from_state}' must be one of the workflow states.")
        if to_state not in states:
            raise ValueError(f"Transition to '{to_state}' must be one of the workflow states.")
        validated.append(WorkflowTransition(from_state=from_state, to_state=to_state))
    return validated


def get_workflow(db: Session, entity_name: str) -> EntityWorkflow | None:
    return (
        db.query(EntityWorkflow)
        .filter(EntityWorkflow.entity_name == entity_name)
        .first()
    )


def get_available_transitions(db: Session, entity_name: str, current_state: str) -> list[str]:
    workflow = get_workflow(db, entity_name)
    if not workflow or not workflow.is_enabled:
        return []
    current_state = _normalize_state(current_state)
    if not current_state:
        return []
    transitions = (
        db.query(EntityTransition)
        .filter(
            EntityTransition.entity_name == entity_name,
            EntityTransition.from_state == current_state,
        )
        .all()
    )
    return [transition.to_state for transition in transitions]


def validate_transition(db: Session, entity_name: str, from_state: str | None, to_state: str) -> bool:
    workflow = get_workflow(db, entity_name)
    if not workflow or not workflow.is_enabled:
        return True
    if from_state is None:
        return False
    from_state = _normalize_state(from_state)
    to_state = _normalize_state(to_state)
    return (
        db.query(EntityTransition)
        .filter(
            EntityTransition.entity_name == entity_name,
            EntityTransition.from_state == from_state,
            EntityTransition.to_state == to_state,
        )
        .count()
        > 0
    )


def create_or_update_workflow(db: Session, workflow_in: WorkflowCreateRequest):
    from app.workflows.services import entity_service
    workflow_in = workflow_in.copy(deep=True)
    workflow_in.validate_workflow()

    # Ensure entity exists before creating workflow config.
    entity_service.get_entity_definition(db, workflow_in.entity_name)

    states = _ensure_unique_states(workflow_in.states)
    initial_state = _normalize_state(workflow_in.initial_state)
    transitions = _validate_transitions(set(states), workflow_in.transitions)

    workflow = get_workflow(db, workflow_in.entity_name)
    if not workflow:
        workflow = EntityWorkflow(
            entity_name=workflow_in.entity_name,
            initial_state=initial_state,
            is_enabled=workflow_in.is_enabled,
        )
        db.add(workflow)
        db.flush()
    else:
        workflow.initial_state = initial_state
        workflow.is_enabled = workflow_in.is_enabled

    # Replace states and transitions atomically for this workflow.
    db.query(EntityState).filter(EntityState.entity_name == workflow_in.entity_name).delete(synchronize_session=False)
    db.query(EntityTransition).filter(EntityTransition.entity_name == workflow_in.entity_name).delete(synchronize_session=False)

    db.add_all(
        [EntityState(entity_name=workflow_in.entity_name, state_name=state) for state in states]
        + [
            EntityTransition(
                entity_name=workflow_in.entity_name,
                from_state=transition.from_state,
                to_state=transition.to_state,
            )
            for transition in transitions
        ]
    )

    db.commit()
    db.refresh(workflow)
    return workflow


def apply_transition(
    db: Session,
    entity_name: str,
    record: EntityRecord,
    new_state: str,
    user_email: str = "system",
) -> None:
    current_state = record.status
    new_state = _normalize_state(new_state)
    if not new_state:
        raise ValueError("Target state must be a non-empty string.")

    workflow = get_workflow(db, entity_name)
    if workflow and workflow.is_enabled:
        if not validate_transition(db, entity_name, current_state, new_state):
            from_state = current_state or "<unset>"
            raise ValueError(f"Invalid transition: {from_state} → {new_state}")

    record.status = new_state
    record.updated_at = _utcnow()

    db.add(EntityStateLog(
        entity_name=entity_name,
        record_id=record.id,
        from_state=current_state,
        to_state=new_state,
        changed_by=user_email,
        changed_at=_utcnow(),
    ))
