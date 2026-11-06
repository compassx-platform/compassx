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
