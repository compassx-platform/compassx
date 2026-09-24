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

router = APIRouter(prefix="/api/v1/ai-gateway/providers", tags=["AI Gateway - Providers"])
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


@router.get("", response_model=list[AIProviderResponse])
def list_providers(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all AI Providers accessible in the current workspace."""
    ws_id = _get_workspace_id(request)
    query = db.query(AIProvider)
    if ws_id:
        query = query.filter((AIProvider.workspace_id == ws_id) | (AIProvider.workspace_id.is_(None)))
    providers = query.order_by(AIProvider.name).all()
    return [_to_provider_response(p) for p in providers]


@router.post("", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    body: AIProviderCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Create a new AI Provider configuration."""
    ws_id = _get_workspace_id(request)

    # Check name duplicate in workspace
    existing_query = db.query(AIProvider).filter(AIProvider.name == body.name)
    if ws_id:
        existing_query = existing_query.filter((AIProvider.workspace_id == ws_id) | (AIProvider.workspace_id.is_(None)))
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Provider with name '{body.name}' already exists.")

    p_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    api_key_enc = encrypt_field(body.api_key) if body.api_key else None
    actor = request.headers.get("X-User-Email") or request.headers.get("X-User-Id") or "system"
    provider = AIProvider(
        workspace_id=ws_id,
        catalog_name=body.catalog_name,
        schema_name=body.schema_name,
        name=body.name,
        provider_type=p_type,
        api_key_enc=api_key_enc,
        base_url=body.base_url,
        config=body.config,
        is_active=body.is_active,
        created_by=body.created_by or actor,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _to_provider_response(provider)


@router.get("/{provider_id}", response_model=AIProviderResponse)
def get_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get AI Provider details by ID."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_provider_response(provider)


@router.put("/{provider_id}", response_model=AIProviderResponse)
def update_provider(
    provider_id: int,
    body: AIProviderUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update AI Provider configuration."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if body.name is not None:
        provider.name = body.name
    if body.provider_type is not None:
        provider.provider_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    if body.catalog_name is not None:
        provider.catalog_name = body.catalog_name
    if body.schema_name is not None:
        provider.schema_name = body.schema_name
    if body.api_key is not None:
        provider.api_key_enc = encrypt_field(body.api_key) if body.api_key else None
    if body.base_url is not None:
        provider.base_url = body.base_url
    if body.config is not None:
        provider.config = body.config
    if body.is_active is not None:
        provider.is_active = body.is_active
    if body.created_by is not None:
        provider.created_by = body.created_by

    db.commit()
    db.refresh(provider)
    return _to_provider_response(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an AI Provider."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return None


@router.post("/discover-models", response_model=AIProviderPingResponse)
async def discover_models(
    body: AIDiscoverModelsRequest,
    request: Request,
):
    """Test connection and discover available models from provider credentials without saving."""
    adapter = get_provider_adapter(body.provider_type)
    creds = ProviderCredentials(
        provider_type=body.provider_type,
        api_key=body.api_key,
        base_url=body.base_url,
        config=body.config or {},
    )

    start_time = time.time()
    try:
        success, message, models = await adapter.ping(creds)
    except Exception as e:
        logger.exception("Error discovering models for provider %s: %s", body.provider_type, e)
        success = False
        message = f"Discovery error: {str(e)}"
        models = []

    latency_ms = int((time.time() - start_time) * 1000)

    return AIProviderPingResponse(
        success=success,
        message=message,
        latency_ms=latency_ms,
        available_models=models,
    )


@router.post("/{provider_id}/ping", response_model=AIProviderPingResponse)
async def ping_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Test connectivity to an external AI Provider."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    plain_key = None
    if provider.api_key_enc:
        try:
            plain_key = decrypt_field(provider.api_key_enc)
        except Exception:
            plain_key = None
    adapter = get_provider_adapter(provider.provider_type)
    creds = ProviderCredentials(
        provider_type=provider.provider_type,
        api_key=plain_key,
        base_url=provider.base_url,
        config=provider.config or {},
    )

    start_time = time.time()
    try:
        success, message, models = await adapter.ping(creds)
    except Exception as e:
        logger.exception("Ping error for provider %s: %s", provider.id, e)
        success = False
        message = f"Ping failed: {str(e)}"
        models = []

    latency_ms = int((time.time() - start_time) * 1000)

    return AIProviderPingResponse(
        success=success,
        message=message,
        latency_ms=latency_ms,
        available_models=models,
    )
