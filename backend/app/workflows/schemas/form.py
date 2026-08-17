"""Pydantic schemas for Form API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FormSchemaResponse(BaseModel):
    id: int
    form_id: str
    entity_name: str
    schema: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True

# Overwrite schema attribute after class creation to avoid Pydantic V2 default-value shadowing conflict
FormSchemaResponse.schema = property(lambda self: self.__dict__.get("schema", {}))


class FormSchemaCreate(BaseModel):
    form_id: str = Field(..., min_length=1)
    entity_name: str = Field(..., min_length=1)
    schema: dict[str, Any] = Field(default_factory=dict)

FormSchemaCreate.schema = property(lambda self: self.__dict__.get("schema", {}))


class FormSchemaUpdate(BaseModel):
    entity_name: str | None = Field(None, min_length=1)
    schema: dict[str, Any] | None = None

FormSchemaUpdate.schema = property(lambda self: self.__dict__.get("schema", None))