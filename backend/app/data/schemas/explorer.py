"""Pydantic schemas for Explorer / Dataset DSL."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExplorerQuery(BaseModel):
    """What the frontend sends to POST /explorer/query."""
    dataset: str = Field(..., min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    select: list[str] = Field(default_factory=list)
    pagination: dict[str, int]
    sort: dict[str, str] | None = None  # {"field": "asc"|"desc"}


class ExplorerRow(BaseModel):
    id: int
    record_id: int
    asset_id: str
    asset_name: str | None = None
    child_asset_id: str | None = None
    child_asset_name: str | None = None
    breakdown_type: str | None = None
    severity: str | None = None
    description: str | None = None
    timestamp: datetime | None = None
    status: str | None = None
    created_by: str | None = None

    class Config:
        from_attributes = True


class ExplorerResponse(BaseModel):
    items: list[ExplorerRow]
    total: int
    page: int
    size: int
    pages: int