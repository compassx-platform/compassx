"""AI Gateway Model Endpoints CRUD and Configuration Routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.orm import Session

from app.ai_gateway.models.provider import AIModelEndpoint, AIProvider

from app.ai_gateway.schemas.provider import (
    AIModelEndpointCreate,
    AIModelEndpointResponse,
    AIModelEndpointUpdate,
)

from app.database import get_account_db

logger = logging.getLogger("app.ai_gateway.routes.endpoint_routes")
def _get_workspace_id(request: Request) -> str | None:
    ctx = getattr(request.state, "workspace", None)
    if ctx and hasattr(ctx, "workspace_id"):
        try:
            import uuid
            uuid.UUID(str(ctx.workspace_id))
            return str(ctx.workspace_id)
        except Exception:
            return None
    ws_header = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id")
    if ws_header:
        try:
            import uuid
            uuid.UUID(str(ws_header))
            return str(ws_header)
        except Exception:
            return None
    return None

def _to_endpoint_response(endpoint: AIModelEndpoint) -> AIModelEndpointResponse:
    provider = endpoint.provider
    return AIModelEndpointResponse(
        id=endpoint.id,
        workspace_id=str(endpoint.workspace_id) if endpoint.workspace_id else None,
        name=endpoint.name,
        provider_id=endpoint.provider_id,
        provider_name=provider.name if provider else None,
        provider_type=provider.provider_type if provider else None,
        upstream_model_name=endpoint.upstream_model_name,
        fallback_endpoint_ids=endpoint.fallback_endpoint_ids or [],
        timeout_s=endpoint.timeout_s,
        max_tokens=endpoint.max_tokens,
        temperature_default=float(endpoint.temperature_default) if endpoint.temperature_default is not None else None,
        rate_limit_rpm=endpoint.rate_limit_rpm,
        rate_limit_tpm=endpoint.rate_limit_tpm,
        input_cost_per_1k_tokens=endpoint.input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=endpoint.output_cost_per_1k_tokens,
        cost_currency=endpoint.cost_currency,
        use_for_embedding=endpoint.use_for_embedding,
        is_default=endpoint.is_default,
        guardrail_config=endpoint.guardrail_config or {},
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )
