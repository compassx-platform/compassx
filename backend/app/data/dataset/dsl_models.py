"""Dataset DSL models – Pydantic contracts for the query language."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DatasetQuery(BaseModel):
    """The canonical DSL for querying datasets through UDAL."""
    dataset: str
    filters: dict[str, Any] = Field(default_factory=dict)
    select: list[str] = Field(default_factory=list)
    aggregation: dict[str, Any] | None = None
    group_by: list[str] = Field(default_factory=list)
    pagination: dict[str, int] = Field(default_factory=lambda: {"page": 1, "size": 50})
    sort: dict[str, str] = Field(default_factory=dict)
