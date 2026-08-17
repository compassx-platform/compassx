from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class WorkflowTransition(BaseModel):
    from_state: str = Field(..., alias="from")
    to_state: str = Field(..., alias="to")

    model_config = {
        "populate_by_name": True,
    }

    @field_validator("from_state", "to_state")
    @classmethod
    def validate_state_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("State names must be non-empty strings.")
        return cleaned


class WorkflowCreateRequest(BaseModel):
    entity_name: str
    initial_state: str
    states: list[str]
    transitions: list[WorkflowTransition]
    is_enabled: bool = True

    @field_validator("entity_name", "initial_state")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Strings must be non-empty.")
        return cleaned

    @field_validator("states")
    @classmethod
    def validate_states(cls, value: list[str]) -> list[str]:
        cleaned = [state.strip() for state in value if state.strip()]
        if not cleaned:
            raise ValueError("Workflow must define at least one state.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Workflow states must be unique.")
        return cleaned

    @field_validator("transitions")
    @classmethod
    def validate_transitions(cls, value: list[WorkflowTransition]) -> list[WorkflowTransition]:
        if not value:
            return value
        return value

    def validate_workflow(self) -> None:
        if self.initial_state not in self.states:
            raise ValueError("initial_state must be one of the workflow states.")
        for transition in self.transitions:
            if transition.from_state not in self.states:
                raise ValueError(f"Transition from '{transition.from_state}' must be one of the workflow states.")
            if transition.to_state not in self.states:
                raise ValueError(f"Transition to '{transition.to_state}' must be one of the workflow states.")


class WorkflowTransitionResponse(BaseModel):
    from_state: str = Field(..., alias="from")
    to_state: str = Field(..., alias="to")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class WorkflowResponse(BaseModel):
    entity_name: str
    initial_state: Optional[str] = None
    is_enabled: bool
    states: list[str]
    transitions: list[WorkflowTransitionResponse]

    model_config = {
        "from_attributes": True,
    }


class AvailableTransitionsResponse(BaseModel):
    available: list[str] = Field(default_factory=list)
