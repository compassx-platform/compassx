"""Pydantic schemas for Entity API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Field type registry (mirrors backend/app/services/field_type_registry.py) ──

CANONICAL_FIELD_TYPES = frozenset({
    "string", "text", "number", "boolean", "time", "datetime", "json"
})


# ── Request schemas ────────────────────────────────────────────────────────────

class EntityFieldCreate(BaseModel):
    field_name: str = Field(..., min_length=1)
    field_type: str = "string"
    is_required: bool = False
    is_indexed: bool = False
    field_source: str = "entity"
    is_system: bool = False
    system_generated: bool = False
    default_value: str | None = None

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        if v not in CANONICAL_FIELD_TYPES:
            raise ValueError(
                f"Invalid field_type '{v}'. Allowed: {sorted(CANONICAL_FIELD_TYPES)}"
            )
        return v


class EntitySystemFieldCreate(BaseModel):
    """Schema for admin-defined system fields (injected server-side)."""
    field_name: str = Field(..., min_length=1)
    field_type: str = "string"
    default_value: str | None = None
    system_generated: bool = False
    is_indexed: bool = False

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        if v not in CANONICAL_FIELD_TYPES:
            raise ValueError(
                f"Invalid field_type '{v}'. Allowed: {sorted(CANONICAL_FIELD_TYPES)}"
            )
        return v


class EntityDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1)
    entity_type: str = "generic"
    asset_scoped: bool = True
    time_based: bool = False
    time_series: bool = True
    fields: list[EntityFieldCreate] = Field(default_factory=list)
    system_fields: list[EntitySystemFieldCreate] = Field(default_factory=list)


class EntityDefinitionUpdate(BaseModel):
    """Partial update for entity definition metadata.

    Name is immutable (it is the unique identifier used in URLs and foreign keys).
    Fields are managed separately via the field sync endpoint.
    """
    entity_type: str | None = None
    asset_scoped: bool | None = None
    time_based: bool | None = None
    time_series: bool | None = None


class EntityFieldUpdate(BaseModel):
    """Partial update for a single entity field (rename, type change, flags)."""
    new_field_name: str | None = None
    field_type: str | None = None
    is_required: bool | None = None
    is_indexed: bool | None = None
    default_value: str | None = None
    system_generated: bool | None = None

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str | None) -> str | None:
        if v is not None and v not in CANONICAL_FIELD_TYPES:
            raise ValueError(
                f"Invalid field_type '{v}'. Allowed: {sorted(CANONICAL_FIELD_TYPES)}"
            )
        return v


class EntityRecordCreate(BaseModel):
    asset_id: str | None = None
    timestamp: datetime | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EntityRecordUpdate(BaseModel):
    asset_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None


# ── Response schemas ───────────────────────────────────────────────────────────

class EntityFieldResponse(BaseModel):
    id: int
    entity_id: int
    field_name: str
    field_type: str
    is_required: bool
    is_indexed: bool
    field_source: str
    is_system: bool
    system_generated: bool
    default_value: str | None

    class Config:
        from_attributes = True


class EntityDefinitionResponse(BaseModel):
    id: int
    name: str
    entity_type: str
    asset_scoped: bool
    time_based: bool
    time_series: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EntityDefinitionDetailResponse(EntityDefinitionResponse):
    """Extended response that includes the field list."""
    fields: list[EntityFieldResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class EntityRecordResponse(BaseModel):
    id: int
    entity_id: int
    asset_id: str | None
    timestamp: datetime
    status: str | None
    data_json: dict[str, Any]
    created_by: str | None
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True