"""Build an in-memory LLMConnection from an AI Gateway model endpoint."""

from __future__ import annotations

import logging

from app.models.agents import LLMConnection, LLMProvider

logger = logging.getLogger(__name__)


def connection_from_gateway_model(model_name: str | None, workspace_id: str | None) -> LLMConnection | None:
    """Resolve a gateway endpoint by name/id and map it onto LLMConnection."""
    name = (model_name or "").strip()
    if not name:
        return None
    try:
        from app.database import AccountSessionLocal
        from app.ai_gateway.services.gateway_service import GatewayService
    except Exception as exc:
        logger.warning("AI Gateway is unavailable for Nova: %s", exc)
        return None
    if AccountSessionLocal is None:
        return None
    db = AccountSessionLocal()
    try:
        endpoint = GatewayService.resolve_endpoint(db, name, workspace_id)
        if endpoint is None or endpoint.provider is None:
            return None
        provider = endpoint.provider
        raw_type = getattr(provider.provider_type, "value", provider.provider_type) or "compatible"
        try:
            llm_provider = LLMProvider(str(raw_type))
        except ValueError:
            llm_provider = LLMProvider.compatible
        conn = LLMConnection(
            name=endpoint.name,
            provider=llm_provider,
            model_name=endpoint.upstream_model_name or endpoint.name,
            api_key_enc=provider.api_key_enc,
            base_url=provider.base_url,
            timeout_s=endpoint.timeout_s or 120,
            max_tokens=endpoint.max_tokens or 8192,
        )
        return conn
    except Exception as exc:
        logger.warning("Failed to map AI Gateway model '%s': %s", name, exc)
        return None
    finally:
        db.close()
