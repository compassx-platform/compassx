"""Pydantic schemas for External Connections."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ExternalConnectionCreate(BaseModel):
    name: str = Field(..., description="User-facing identifier, e.g. 'loki_prod'")
    connector_type: str = Field(default="loki", description="Connector type / label, e.g. 'loki', 'prometheus', 'custom'")
    base_url: str = Field(..., description="Base URL of the external service")
    auth_config: Optional[Union[dict[str, Any], str]] = Field(default=None, description="Sensitive auth configuration / token (will be encrypted at rest)")
    status: str = Field(default="active", description="'active' | 'disabled'")


class ExternalConnectionUpdate(BaseModel):
    name: Optional[str] = None
    connector_type: Optional[str] = None
    base_url: Optional[str] = None
    auth_config: Optional[Union[dict[str, Any], str]] = None
    status: Optional[str] = None


class ExternalConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: Optional[str] = None
    name: str
    connector_type: str
    base_url: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
