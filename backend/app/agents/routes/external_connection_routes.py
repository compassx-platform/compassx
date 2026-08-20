"""API routes for managing External Connections (Loki, Prometheus, REST APIs)."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db
from app.dependencies import get_current_user
from app.agents.schemas.external_connections import (
    ExternalConnectionCreate,
    ExternalConnectionResponse,
    ExternalConnectionUpdate,
)
from app.agents.services import external_connection_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["External Connections"])


def _to_response(conn) -> ExternalConnectionResponse:
    return ExternalConnectionResponse(
        id=str(conn.id),
        workspace_id=str(conn.workspace_id) if conn.workspace_id else None,
        name=conn.name,
        connector_type=conn.connector_type,
        base_url=conn.base_url,
        status=conn.status,
        created_by=conn.created_by,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.post(
    "/api/v1/external-connections",
    response_model=ExternalConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/external-connections",
    response_model=ExternalConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_external_connection(
    payload: ExternalConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace_id", None)
    user_id = getattr(current_user, "id", "default_user")
    if hasattr(user_id, "__str__"):
        user_id = str(user_id)

    try:
        conn = svc.create_connection(
            db=db,
            data=payload,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return _to_response(conn)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/api/v1/external-connections",
    response_model=List[ExternalConnectionResponse],
)
@router.get(
    "/external-connections",
    response_model=List[ExternalConnectionResponse],
    include_in_schema=False,
)
def list_external_connections(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace_id", None)
    conns = svc.list_connections(db, workspace_id=workspace_id, status=status_filter)
    return [_to_response(c) for c in conns]


@router.get(
    "/api/v1/external-connections/{connection_id}",
    response_model=ExternalConnectionResponse,
)
@router.get(
    "/external-connections/{connection_id}",
    response_model=ExternalConnectionResponse,
    include_in_schema=False,
)
def get_external_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace_id", None)
    conn = svc.get_connection(db, connection_id, workspace_id=workspace_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"External connection '{connection_id}' not found.")
    return _to_response(conn)


@router.put(
    "/api/v1/external-connections/{connection_id}",
    response_model=ExternalConnectionResponse,
)
@router.put(
    "/external-connections/{connection_id}",
    response_model=ExternalConnectionResponse,
    include_in_schema=False,
)
@router.patch(
    "/api/v1/external-connections/{connection_id}",
    response_model=ExternalConnectionResponse,
)
def update_external_connection(
    connection_id: str,
    payload: ExternalConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace_id", None)
    try:
        conn = svc.update_connection(db, connection_id, payload, workspace_id=workspace_id)
        return _to_response(conn)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/api/v1/external-connections/{connection_id}/disable",
    response_model=ExternalConnectionResponse,
)
@router.post(
    "/external-connections/{connection_id}/disable",
    response_model=ExternalConnectionResponse,
    include_in_schema=False,
)
def disable_external_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace_id", None)
    try:
        conn = svc.disable_connection(db, connection_id, workspace_id=workspace_id)
        return _to_response(conn)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/api/v1/external-connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@router.delete(
    "/external-connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def delete_external_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace_id", None)
    deleted = svc.delete_connection(db, connection_id, workspace_id=workspace_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"External connection '{connection_id}' not found.")
    return None
