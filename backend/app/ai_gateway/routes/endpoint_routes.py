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

router = APIRouter(prefix="/api/v1/ai-gateway/endpoints", tags=["AI Gateway - Model Endpoints"])
logger = logging.getLogger(__name__)


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


@router.get("", response_model=list[AIModelEndpointResponse])
def list_endpoints(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all AI Model Endpoints for the workspace."""
    ws_id = _get_workspace_id(request)
    query = db.query(AIModelEndpoint)
    if ws_id:
        query = query.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
    endpoints = query.order_by(AIModelEndpoint.name).all()
    return [_to_endpoint_response(ep) for ep in endpoints]


@router.post("", response_model=AIModelEndpointResponse, status_code=status.HTTP_201_CREATED)
def create_endpoint(
    body: AIModelEndpointCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Create a new AI Model Endpoint."""
    ws_id = _get_workspace_id(request)

    # Verify provider exists
    provider = db.query(AIProvider).filter(AIProvider.id == body.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail=f"Provider with ID {body.provider_id} not found.")

    # Check unique name
    existing_query = db.query(AIModelEndpoint).filter(AIModelEndpoint.name == body.name)
    if ws_id:
        existing_query = existing_query.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Endpoint with alias '{body.name}' already exists.")

    if body.is_default and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"is_default": False})

    if body.use_for_embedding and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"use_for_embedding": False})

    endpoint = AIModelEndpoint(
        workspace_id=ws_id,
        name=body.name,
        provider_id=body.provider_id,
        upstream_model_name=body.upstream_model_name,
        fallback_endpoint_ids=body.fallback_endpoint_ids,
        timeout_s=body.timeout_s,
        max_tokens=body.max_tokens,
        temperature_default=body.temperature_default,
        rate_limit_rpm=body.rate_limit_rpm,
        rate_limit_tpm=body.rate_limit_tpm,
        input_cost_per_1k_tokens=body.input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=body.output_cost_per_1k_tokens,
        cost_currency=body.cost_currency,
        use_for_embedding=body.use_for_embedding,
        is_default=body.is_default,
        guardrail_config=body.guardrail_config,
        is_active=body.is_active,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)


@router.get("/{endpoint_id}", response_model=AIModelEndpointResponse)
def get_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get AI Model Endpoint by ID."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return _to_endpoint_response(endpoint)


@router.put("/{endpoint_id}", response_model=AIModelEndpointResponse)
def update_endpoint(
    endpoint_id: int,
    body: AIModelEndpointUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update AI Model Endpoint."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    ws_id = _get_workspace_id(request)
    if body.is_default and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"is_default": False})

    if body.use_for_embedding and ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"use_for_embedding": False})

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(endpoint, field, value)

    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an AI Model Endpoint."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    db.delete(endpoint)
    db.commit()
    return None


@router.post("/{endpoint_id}/set-default", response_model=AIModelEndpointResponse)
def set_default_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Set endpoint as the default model endpoint for the workspace."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    ws_id = _get_workspace_id(request)
    if ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"is_default": False})
    endpoint.is_default = True
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)


@router.post("/{endpoint_id}/set-embedding", response_model=AIModelEndpointResponse)
def set_embedding_endpoint(
    endpoint_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Set endpoint as the active embedding model endpoint."""
    endpoint = db.query(AIModelEndpoint).filter(AIModelEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    ws_id = _get_workspace_id(request)
    if ws_id:
        db.query(AIModelEndpoint).filter(AIModelEndpoint.workspace_id == ws_id).update({"use_for_embedding": False})
    endpoint.use_for_embedding = True
    db.commit()
    db.refresh(endpoint)
    return _to_endpoint_response(endpoint)
