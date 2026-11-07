"""AI Gateway Provider CRUD and Ping Routes."""

from __future__ import annotations

import logging

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.orm import Session

from app.ai_gateway.models.provider import AIModelEndpoint, AIProvider, AIProviderType

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


def _unique_endpoint_name(db: Session, alias: str, workspace_id: str | None, provider_id: int) -> str:
    name = (alias or "model")[:100]
    query = db.query(AIModelEndpoint).filter(AIModelEndpoint.name == name)
    if workspace_id:
        query = query.filter((AIModelEndpoint.workspace_id == workspace_id) | (AIModelEndpoint.workspace_id.is_(None)))
    clash = query.first()
    if clash and clash.provider_id != provider_id:
        suffix = f"-{provider_id}"
        name = (alias[: max(1, 100 - len(suffix))] + suffix)[:100]
    return name


def _sync_provider_endpoints(
    db: Session,
    provider: AIProvider,
    model_names: list[str] | None,
    workspace_id: str | None,
) -> None:
    if model_names is None:
        return
    wanted: list[str] = []
    seen: set[str] = set()
    for raw in model_names:
        item = " ".join(str(raw).split())
        if not item or item in seen:
            continue
        seen.add(item)
        wanted.append(item[:100])
    wanted_set = set(wanted)
    existing = db.query(AIModelEndpoint).filter(AIModelEndpoint.provider_id == provider.id).all()
    for endpoint in existing:
        if endpoint.upstream_model_name not in wanted_set:
            db.delete(endpoint)
    remaining = {
        endpoint.upstream_model_name
        for endpoint in existing
        if endpoint.upstream_model_name in wanted_set
    }
    used_names = {
        endpoint.name for endpoint in existing if endpoint.upstream_model_name in wanted_set
    }
    has_default = any(endpoint.is_default for endpoint in existing if endpoint.upstream_model_name in wanted_set)
    for index, model in enumerate(wanted):
        if model in remaining:
            continue
        alias = _unique_endpoint_name(db, model, workspace_id, provider.id)
        if alias in used_names:
            alias = f"{model}-{provider.id}"[:100]
        used_names.add(alias)
        endpoint = AIModelEndpoint(
            workspace_id=workspace_id,
            name=alias,
            provider_id=provider.id,
            upstream_model_name=model,
            is_active=True,
            is_default=not has_default and index == 0,
            use_for_embedding="embed" in model.lower(),
        )
        db.add(endpoint)
        if endpoint.is_default:
            has_default = True
