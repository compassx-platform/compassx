"""Pydantic schemas for Catalog Tools and Tool Promotion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolPromoteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str = Field(..., description="Tool name, e.g. 'get_last_5_min_logs'")
    catalog: str = Field(default="main", description="Catalog name")
    schema_name: str = Field(default="default", alias="schema", description="Schema name")
    source_code: str = Field(..., description="The promoted Python function body")
    source_notebook_object_id: Optional[str] = Field(default=None, description="Provenance - notebook object id")
    notebook: Optional[str] = Field(default=None, description="Alias for notebook path/id")
    notebook_path: Optional[str] = Field(default=None, description="Alias for notebook path")
    param_schema: Optional[dict[str, Any]] = Field(default=None, description="Explicit parameter JSON Schema")
    description: Optional[str] = Field(default=None, description="Tool description shown in manifest")
    connection_dependencies: Optional[List[str]] = Field(default=None, description="List of connection names / UUIDs")


class ToolVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool_id: str
    version: int
    source_notebook_object_id: Optional[str] = None
    source_code: str
    param_schema: dict[str, Any]
    connection_dependencies: List[str]
    promoted_by: str
    promoted_at: datetime


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    catalog: str = Field(alias="catalog_name")
    schema_name: str = Field(alias="schema_name")
    name: str
    full_name: str
    description: Optional[str] = None
    param_schema: dict[str, Any]
    connection_dependencies: List[str]
    source_notebook_object_id: Optional[str] = None
    source_code: str
    owner: str
    current_version: int
    created_at: datetime
    updated_at: datetime
    versions: List[ToolVersionResponse] = []
