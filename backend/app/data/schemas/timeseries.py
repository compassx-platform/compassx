"""Pydantic schemas for the time-series data editor module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Query / response
# ---------------------------------------------------------------------------

class TimeseriesRow(BaseModel):
    """A single enriched time-series row returned by the query API."""

    ts: datetime
    asset_id: int
    asset_name: str = ""
    tag_def_id: int
    tag_name: str = ""
    value: float | None

    model_config = {"from_attributes": True}


class TimeseriesQueryResponse(BaseModel):
    items: list[TimeseriesRow]
    total: int
    page: int
    size: int
    pages: int


# ---------------------------------------------------------------------------
# Batch update (inline editing)
# ---------------------------------------------------------------------------

class BatchUpdateItem(BaseModel):
    """One row in a batch-update payload."""

    ts: datetime
    asset_id: int
    tag_def_id: int
    value: float

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, v: float) -> float:
        import math
        if math.isnan(v) or math.isinf(v):
            raise ValueError("value must be a finite number")
        return v


class BatchUpdateRequest(BaseModel):
    rows: list[BatchUpdateItem] = Field(..., min_length=1)


class BatchUpdateResponse(BaseModel):
    updated: int
    inserted: int


# ---------------------------------------------------------------------------
# Upload – staging row representation
# ---------------------------------------------------------------------------

class StagingRowOut(BaseModel):
    """Staging row as returned in diff / validation responses."""

    row_number: int
    ts: datetime | None
    asset_ref: str | None
    tag_ref: str | None
    value: float | None
    asset_id: int | None
    tag_def_id: int | None
    status: str
    error_message: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Upload flow responses
# ---------------------------------------------------------------------------

class UploadInitResponse(BaseModel):
    batch_id: str
    row_count: int


class ValidateResponse(BaseModel):
    batch_id: str
    valid_count: int
    invalid_count: int
    duplicate_count: int
    new_count: int
    updated_count: int


class DiffResponse(BaseModel):
    batch_id: str
    new: list[StagingRowOut]
    updated: list[StagingRowOut]
    duplicate: list[StagingRowOut]
    invalid: list[StagingRowOut]


class ApplyResponse(BaseModel):
    batch_id: str
    applied: int
    skipped: int


# ---------------------------------------------------------------------------
# Tag definitions
# ---------------------------------------------------------------------------

class TagDefinitionOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}
