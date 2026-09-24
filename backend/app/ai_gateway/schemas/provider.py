"""Pydantic schemas for AI Gateway Providers and Endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai_gateway.models.provider import AIProviderType


# --- Provider Schemas ---

class AIProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: AIProviderType
    catalog_name: str | None = None
    schema_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_by: str | None = None


class AIProviderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    provider_type: AIProviderType | None = None
    catalog_name: str | None = None
    schema_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None
    created_by: str | None = None


class AIProviderResponse(BaseModel):
    id: int
    workspace_id: UUID | str | None
    catalog_name: str | None = None
    schema_name: str | None = None
    name: str
    provider_type: AIProviderType
    has_api_key: bool
    masked_api_key: str | None = None
    base_url: str | None
    config: dict[str, Any]
    is_active: bool
    created_by: str | None = "system"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIProviderPingResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int = 0
    available_models: list[str] = Field(default_factory=list)


class AIDiscoverModelsRequest(BaseModel):
    provider_type: AIProviderType
    api_key: str | None = None
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


# --- Endpoint Schemas ---

class AIModelEndpointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_id: int
    upstream_model_name: str = Field(..., min_length=1, max_length=100)
    fallback_endpoint_ids: list[int] = Field(default_factory=list)
    timeout_s: int = Field(default=120, ge=1, le=600)
    max_tokens: int = Field(default=8192, ge=1)
    temperature_default: float | None = Field(default=0.7, ge=0.0, le=2.0)
    rate_limit_rpm: int | None = Field(default=None, ge=1)
    rate_limit_tpm: int | None = Field(default=None, ge=1)
    input_cost_per_1k_tokens: Decimal | None = None
    output_cost_per_1k_tokens: Decimal | None = None
    cost_currency: str = "USD"
    use_for_embedding: bool = False
    is_default: bool = False
    guardrail_config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AIModelEndpointUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    provider_id: int | None = None
    upstream_model_name: str | None = Field(None, min_length=1, max_length=100)
    fallback_endpoint_ids: list[int] | None = None
    timeout_s: int | None = Field(None, ge=1, le=600)
    max_tokens: int | None = Field(None, ge=1)
    temperature_default: float | None = Field(None, ge=0.0, le=2.0)
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    input_cost_per_1k_tokens: Decimal | None = None
    output_cost_per_1k_tokens: Decimal | None = None
    cost_currency: str | None = None
    use_for_embedding: bool | None = None
    is_default: bool | None = None
    guardrail_config: dict[str, Any] | None = None
    is_active: bool | None = None


class AIModelEndpointResponse(BaseModel):
    id: int
    workspace_id: UUID | str | None
    name: str
    provider_id: int
    provider_name: str | None = None
    provider_type: AIProviderType | None = None
    upstream_model_name: str
    fallback_endpoint_ids: list[int]
    timeout_s: int
    max_tokens: int
    temperature_default: float | None
    rate_limit_rpm: int | None
    rate_limit_tpm: int | None
    input_cost_per_1k_tokens: Decimal | None
    output_cost_per_1k_tokens: Decimal | None
    cost_currency: str | None
    use_for_embedding: bool
    is_default: bool
    guardrail_config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
