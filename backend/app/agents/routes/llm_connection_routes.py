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

router = APIRouter(prefix="/api/v1/llm-connections", tags=["LLM Connections"])
logger = logging.getLogger(__name__)


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


@router.get("", response_model=list[LLMConnectionResponse])
def list_llm_connections(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the model connections the caller may see.

    The API key comes back masked, never in full — the stored value is only
    decrypted to compute the mask and when a call is actually made.
    """
    rows = (
        db.query(LLMConnection)
        .filter(LLMConnection.workspace_id == guard.workspace_id)
        .order_by(LLMConnection.name)
        .all()
    )
    return [_to_response(r) for r in visible_connections(guard, rows)]


@router.post("", response_model=LLMConnectionResponse, status_code=201)
def create_llm_connection(
    request: Request,
    body: LLMConnectionCreate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Register a model provider.

    Admin, for the same reason as a database connection: it stores a credential
    that anyone later granted USE_COMPUTE can spend against.
    """
    guard.require_workspace_admin("Creating an LLM connection")
    workspace_id = guard.workspace_id
    if body.use_for_embedding:
        db.query(LLMConnection).filter(LLMConnection.workspace_id == workspace_id).update({LLMConnection.use_for_embedding: False})

    username = str(guard.principal.id)

    conn = LLMConnection(
        workspace_id=workspace_id,
        name=body.name,
        provider=body.provider,
        model_name=body.model_name,
        api_key_enc=encrypt_field(body.api_key) if body.api_key else None,
        base_url=body.base_url,
        timeout_s=body.timeout_s,
        max_tokens=body.max_tokens,
        config=body.config,
        is_fallback=body.is_fallback,
        use_for_embedding=body.use_for_embedding,
        input_cost_per_1k_tokens=body.input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=body.output_cost_per_1k_tokens,
        cost_currency=body.cost_currency or "USD",
        cost_configured_at=datetime.now(timezone.utc) if body.input_cost_per_1k_tokens is not None else None,
        cost_configured_by=username if body.input_cost_per_1k_tokens is not None else None,
    )
    db.add(conn)
    try:
        db.commit()
        db.refresh(conn)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to save LLM connection: {exc}") from exc
    guard.claim_ownership(Securable.connection(str(conn.id)))
    return _to_response(conn)


@router.get("/{connection_id}", response_model=LLMConnectionResponse)
def get_llm_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    return _to_response(_get_or_404(db, connection_id, guard, Privilege.BROWSE))


@router.put("/{connection_id}", response_model=LLMConnectionResponse)
def update_llm_connection(
    request: Request,
    connection_id: int,
    body: LLMConnectionUpdate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Change a model connection.

    EDIT: this can repoint the connection at a different provider or key while
    everyone granted on it keeps calling it.
    """
    workspace_id = guard.workspace_id
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    data = body.model_dump(exclude_none=True)
    if data.get("use_for_embedding"):
        db.query(LLMConnection).filter(LLMConnection.workspace_id == workspace_id).update({LLMConnection.use_for_embedding: False})
    if "api_key" in data:
        conn.api_key_enc = encrypt_field(data.pop("api_key"))
    
    # Check if cost was updated to set metadata
    has_cost_update = "input_cost_per_1k_tokens" in data or "output_cost_per_1k_tokens" in data or "cost_currency" in data
    if has_cost_update:
        username = str(guard.principal.id)
        conn.cost_configured_at = datetime.now(timezone.utc)
        conn.cost_configured_by = username

    for field, value in data.items():
        setattr(conn, field, value)
    try:
        db.commit()
        db.refresh(conn)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to update LLM connection: {exc}") from exc
    return _to_response(conn)


@router.post("/{connection_id}/set-embedding", response_model=LLMConnectionResponse)
def set_embedding_llm(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Mark a single LLM connection as the embedding provider (exclusive toggle).

    Admin, not EDIT on the one connection: the toggle is workspace-wide, and it
    clears the flag on every other connection, including ones the caller may
    hold no grant on at all. It also decides which provider every future
    embedding — and so the content of every indexed document — is sent to.
    """
    guard.require_workspace_admin("Choosing the embedding model")
    workspace_id = guard.workspace_id
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    db.query(LLMConnection).filter(LLMConnection.workspace_id == workspace_id).update({LLMConnection.use_for_embedding: False})
    conn.use_for_embedding = True
    try:
        db.commit()
        db.refresh(conn)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to set embedding LLM connection: {exc}") from exc
    return _to_response(conn)


@router.delete("/{connection_id}", status_code=204)
def delete_llm_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a model connection.

    MANAGE: every agent bound to it stops working, and the grants go with it.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.MANAGE)
    db.delete(conn)
    db.commit()


@router.post("/{connection_id}/ping", response_model=PingResponse)
async def ping_llm_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Send a probe request to the provider.

    USE_COMPUTE: it spends the stored key on a real API call, so it takes the
    privilege that calling through the connection takes.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    success, error = await llm_ping(conn)
    return PingResponse(success=success, message="Connection successful" if success else f"Connection failed: {error}")


def _get_or_404(db: Session, connection_id: int, guard: Guard, privilege: Privilege) -> LLMConnection:
    """Load a model connection the caller holds ``privilege`` on.

    Workspace comes from the guard. The previous version fell back to
    ``workspace_id == None`` when none was resolved, so an unscoped request
    reached the workspace-less connections rather than being refused.
    """
    return authorized_connection(db, guard, LLMConnection, connection_id, privilege)
