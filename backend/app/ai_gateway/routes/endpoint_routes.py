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

import app.ai_gateway.http.endpoints.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.ai_gateway.http.endpoints.application.list_endpoints import list_endpoints as list_endpoints_action
from app.ai_gateway.http.endpoints.application.create_endpoint import create_endpoint as create_endpoint_action
from app.ai_gateway.http.endpoints.application.get_endpoint import get_endpoint as get_endpoint_action
from app.ai_gateway.http.endpoints.application.update_endpoint import update_endpoint as update_endpoint_action
from app.ai_gateway.http.endpoints.application.delete_endpoint import delete_endpoint as delete_endpoint_action
from app.ai_gateway.http.endpoints.application.set_default_endpoint import set_default_endpoint as set_default_endpoint_action
from app.ai_gateway.http.endpoints.application.set_embedding_endpoint import set_embedding_endpoint as set_embedding_endpoint_action

logger = logging.getLogger("app.ai_gateway.routes.endpoint_routes")

router = APIRouter(prefix="/api/v1/ai-gateway/endpoints", tags=["AI Gateway - Model Endpoints"])

@router.get("", response_model=list[AIModelEndpointResponse])
def list_endpoints(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all AI Model Endpoints for the workspace."""
    return list_endpoints_action(request=request, db=db)

@router.post("", response_model=AIModelEndpointResponse, status_code=status.HTTP_201_CREATED)
def create_endpoint(
    body: AIModelEndpointCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Create a new AI Model Endpoint."""
    return create_endpoint_action(body=body, request=request, db=db)

@router.get("/{endpoint_id}", response_model=AIModelEndpointResponse)
def get_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get AI Model Endpoint by ID."""
    return get_endpoint_action(endpoint_id=endpoint_id, request=request, db=db)

@router.put("/{endpoint_id}", response_model=AIModelEndpointResponse)
def update_endpoint(
    endpoint_id: int,
    body: AIModelEndpointUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update AI Model Endpoint."""
    return update_endpoint_action(endpoint_id=endpoint_id, body=body, request=request, db=db)

@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an AI Model Endpoint."""
    return delete_endpoint_action(endpoint_id=endpoint_id, request=request, db=db)

@router.post("/{endpoint_id}/set-default", response_model=AIModelEndpointResponse)
def set_default_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Set endpoint as the default model endpoint for the workspace."""
    return set_default_endpoint_action(endpoint_id=endpoint_id, request=request, db=db)

@router.post("/{endpoint_id}/set-embedding", response_model=AIModelEndpointResponse)
def set_embedding_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Set endpoint as the active embedding model endpoint."""
    return set_embedding_endpoint_action(endpoint_id=endpoint_id, request=request, db=db)
