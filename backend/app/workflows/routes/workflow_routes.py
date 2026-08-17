from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.database import get_db
from app.schemas.workflow import (
    AvailableTransitionsResponse,
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowTransitionResponse,
)
from app.services import entity_service, state_machine_service

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def _build_workflow_response(workflow) -> WorkflowResponse:
    return WorkflowResponse(
        entity_name=workflow.entity_name,
        initial_state=workflow.initial_state,
        is_enabled=workflow.is_enabled,
        states=[state.state_name for state in workflow.states],
        transitions=[
            WorkflowTransitionResponse(from_state=transition.from_state, to_state=transition.to_state)
            for transition in workflow.transitions
        ],
    )


@router.post("", response_model=WorkflowResponse, status_code=201)
def create_workflow(
    body: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        workflow = state_machine_service.create_or_update_workflow(db, body)
        return _build_workflow_response(workflow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unable to save workflow: {exc}")


@router.get("/{entity_name}", response_model=WorkflowResponse)
def get_workflow(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        entity_service.get_entity_definition(db, entity_name)
        workflow = state_machine_service.get_workflow(db, entity_name)
        if not workflow:
            # Workflows are optional; return empty workflow config
            return WorkflowResponse(
                entity_name=entity_name,
                initial_state=None,
                is_enabled=False,
                states=[],
                transitions=[],
            )
        return _build_workflow_response(workflow)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to load workflow: {exc}")


@router.get("/{entity_name}/transitions", response_model=AvailableTransitionsResponse)
def get_available_transitions(
    entity_name: str,
    current_state: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        entity_service.get_entity_definition(db, entity_name)
        transitions = state_machine_service.get_available_transitions(db, entity_name, current_state)
        return AvailableTransitionsResponse(available=transitions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to load transitions: {exc}")
