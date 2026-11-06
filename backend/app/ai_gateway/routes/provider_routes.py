"""AI Gateway Provider CRUD and Ping Routes."""

from __future__ import annotations

import logging

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.orm import Session

from app.ai_gateway.models.provider import AIProvider, AIProviderType

from app.ai_gateway.providers.base import ProviderCredentials

from app.ai_gateway.providers.factory import get_provider_adapter

from app.ai_gateway.schemas.provider import (
    AIDiscoverModelsRequest,
    AIProviderCreate,
    AIProviderPingResponse,
    AIProviderResponse,
    AIProviderUpdate,
)

from app.ai_gateway.services.gateway_service import GatewayService

from app.database import get_account_db

from app.services.encryption import decrypt_field, encrypt_field, mask_key

logger = logging.getLogger("app.ai_gateway.routes.provider_routes")
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

def _to_provider_response(provider: AIProvider) -> AIProviderResponse:
    plain_key = None
    if provider.api_key_enc:
        try:
            plain_key = decrypt_field(provider.api_key_enc)
        except Exception:
            logger.warning("Could not decrypt api_key_enc for provider %s", provider.id)

    raw_p_type = provider.provider_type
    try:
        p_enum = AIProviderType(raw_p_type)
    except Exception:
        p_enum = AIProviderType.compatible

    return AIProviderResponse(
        id=provider.id,
        workspace_id=str(provider.workspace_id) if provider.workspace_id else None,
        catalog_name=provider.catalog_name,
        schema_name=provider.schema_name,
        name=provider.name,
        provider_type=p_enum,
        has_api_key=bool(provider.api_key_enc),
        masked_api_key=mask_key(plain_key) if plain_key else None,
        base_url=provider.base_url,
        config=provider.config or {},
        is_active=provider.is_active,
        created_by=getattr(provider, "created_by", None) or "system",
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )

import app.ai_gateway.http.providers.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.ai_gateway.http.providers.application.list_providers import list_providers as list_providers_action
from app.ai_gateway.http.providers.application.create_provider import create_provider as create_provider_action
from app.ai_gateway.http.providers.application.get_provider import get_provider as get_provider_action
from app.ai_gateway.http.providers.application.update_provider import update_provider as update_provider_action
from app.ai_gateway.http.providers.application.delete_provider import delete_provider as delete_provider_action
from app.ai_gateway.http.providers.application.discover_models import discover_models as discover_models_action
from app.ai_gateway.http.providers.application.ping_provider import ping_provider as ping_provider_action

logger = logging.getLogger("app.ai_gateway.routes.provider_routes")

router = APIRouter(prefix="/api/v1/ai-gateway/providers", tags=["AI Gateway - Providers"])

@router.get("", response_model=list[AIProviderResponse])
def list_providers(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all AI Providers accessible in the current workspace."""
    return list_providers_action(request=request, db=db)

@router.post("", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    body: AIProviderCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Create a new AI Provider configuration."""
    return create_provider_action(body=body, request=request, db=db)

@router.get("/{provider_id}", response_model=AIProviderResponse)
def get_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get AI Provider details by ID."""
    return get_provider_action(provider_id=provider_id, request=request, db=db)

@router.put("/{provider_id}", response_model=AIProviderResponse)
def update_provider(
    provider_id: int,
    body: AIProviderUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update AI Provider configuration."""
    return update_provider_action(provider_id=provider_id, body=body, request=request, db=db)

@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an AI Provider."""
    return delete_provider_action(provider_id=provider_id, request=request, db=db)

@router.post("/discover-models", response_model=AIProviderPingResponse)
async def discover_models(
    body: AIDiscoverModelsRequest,
    request: Request,
):
    """Test connection and discover available models from provider credentials without saving."""
    return await discover_models_action(body=body, request=request)

@router.post("/{provider_id}/ping", response_model=AIProviderPingResponse)
async def ping_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Test connectivity to an external AI Provider."""
    return await ping_provider_action(provider_id=provider_id, request=request, db=db)
