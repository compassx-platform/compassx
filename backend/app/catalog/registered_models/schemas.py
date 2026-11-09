"""Request and response shapes for catalog registered models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


_NAME = r"^[A-Za-z][A-Za-z0-9_-]{0,126}$"
_ALIAS = r"^[A-Za-z][A-Za-z0-9_-]{0,62}$"


class ModelCreate(BaseModel):
    name: str = Field(..., pattern=_NAME)
    comment: str | None = None


class ModelUpdate(BaseModel):
    comment: str | None = None
    owner: str | None = None


class ModelVersionCreate(BaseModel):
    """Register a new version from an MLflow run.

    ``artifact_path`` empty means every file logged on the run. A relative
    path such as ``model`` or ``autoencoder.pt`` copies only that artifact.
    """

    run_id: str = Field(..., min_length=1, max_length=64)
    artifact_path: str = ""
    comment: str | None = None
    alias: str | None = Field(None, pattern=_ALIAS)


class ModelAliasSet(BaseModel):
    alias: str = Field(..., pattern=_ALIAS)
    version: int = Field(..., ge=1)


class ModelAliasRead(BaseModel):
    alias: str
    version: int


class ModelVersionRead(BaseModel):
    version: int
    run_id: str | None = None
    source: str
    artifact_path: str
    status: str
    comment: str | None = None
    storage_location: str | None = None
    files: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    created_by: str
    created_at: datetime


class RegisteredModelRead(BaseModel):
    id: str
    catalog_name: str
    schema_name: str
    name: str
    full_name: str
    comment: str | None = None
    owner: str
    storage_location: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    aliases: list[ModelAliasRead] = Field(default_factory=list)
    versions: list[ModelVersionRead] = Field(default_factory=list)


class RegisteredModelSummary(BaseModel):
    id: str
    catalog_name: str
    schema_name: str
    name: str
    full_name: str
    comment: str | None = None
    owner: str
    updated_at: datetime
    latest_version: int | None = None
    aliases: list[ModelAliasRead] = Field(default_factory=list)
