"""Pydantic schemas for Unified Catalog Connections."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConnectionFieldSchema(BaseModel):
    name: str
    label: str
    type: str = "text"
    required: bool = True
    default: Any = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[dict[str, str]]] = None


class ProviderMetadataResponse(BaseModel):
    type_id: str
    name: str
    category: str
    description: str
    is_popular: bool = False
    logo: str
    default_port: Optional[int] = None
    config_fields: List[ConnectionFieldSchema] = []
    auth_fields: List[ConnectionFieldSchema] = []


class CatalogConnectionCreate(BaseModel):
    catalog: Optional[str] = Field(default=None, description="Catalog name (optional for account-level)")
    schema_name: Optional[str] = Field(default=None, alias="schema", description="Schema name (optional for account-level)")
    name: str = Field(..., description="Unique connection identifier")
    connector_type: str = Field(..., description="Connector type (e.g. postgres, rest_api, loki)")
    category: Optional[str] = Field(default=None, description="Category (database, api, observability, custom)")
    description: Optional[str] = Field(default=None, description="Optional description")
    config: dict[str, Any] = Field(default_factory=dict, description="Non-sensitive connection configuration")
    auth_config: Optional[Any] = Field(default=None, description="Sensitive credentials (encrypted at rest)")
    status: Optional[str] = Field(default="active", description="active | disabled")


class CatalogConnectionUpdate(BaseModel):
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    auth_config: Optional[Any] = None
    status: Optional[str] = None


class CatalogConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    catalog: Optional[str] = Field(default=None, validation_alias="catalog_name")
    schema_name: Optional[str] = None
    name: str
    full_name: str
    category: str
    connector_type: str
    description: Optional[str] = None
    config: dict[str, Any]
    status: str
    owner: str
    created_at: datetime
    updated_at: datetime


class ConnectionTestRequest(BaseModel):
    connector_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    auth_config: Optional[Any] = None
    connection_id: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int = 0
    details: Optional[dict[str, Any]] = None
