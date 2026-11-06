"""LLM Connection CRUD routes + ping endpoint."""

from __future__ import annotations

import logging

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_connection, visible_connections

from app.database import get_account_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.governance.securable import Securable

from app.models.agents import LLMConnection

from app.schemas.agents import LLMConnectionCreate, LLMConnectionResponse, LLMConnectionUpdate, PingResponse

from app.services.encryption import decrypt_field, encrypt_field, mask_key

from app.services.llm_client import ping as llm_ping

logger = logging.getLogger("app.agents.routes.llm_connection_routes")

def _to_response(conn: LLMConnection) -> LLMConnectionResponse:
    plain_key = ""
    if conn.api_key_enc:
        try:
            plain_key = decrypt_field(conn.api_key_enc)
        except ValueError:
            logger.warning("Skipping unreadable api_key_enc for LLM connection %s", conn.id)
    return LLMConnectionResponse(
        id=conn.id,
        name=conn.name,
        provider=conn.provider,
        model_name=conn.model_name,
        api_key_masked=mask_key(plain_key) if plain_key else None,
        base_url=conn.base_url,
        timeout_s=conn.timeout_s,
        max_tokens=conn.max_tokens,
        config=conn.config or {},
        is_fallback=conn.is_fallback,
        use_for_embedding=conn.use_for_embedding,
        input_cost_per_1k_tokens=float(conn.input_cost_per_1k_tokens) if conn.input_cost_per_1k_tokens is not None else None,
        output_cost_per_1k_tokens=float(conn.output_cost_per_1k_tokens) if conn.output_cost_per_1k_tokens is not None else None,
        cost_currency=conn.cost_currency,
        cost_configured_at=conn.cost_configured_at,
        cost_configured_by=conn.cost_configured_by,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )

def _get_or_404(db: Session, connection_id: int, guard: Guard, privilege: Privilege) -> LLMConnection:
    """Load a model connection the caller holds ``privilege`` on.

    Workspace comes from the guard. The previous version fell back to
    ``workspace_id == None`` when none was resolved, so an unscoped request
    reached the workspace-less connections rather than being refused.
    """
    return authorized_connection(db, guard, LLMConnection, connection_id, privilege)
