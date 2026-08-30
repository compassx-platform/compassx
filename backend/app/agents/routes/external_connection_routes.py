"""API routes for managing External Connections (Loki, Prometheus, REST APIs).

An external connection is a base URL plus an encrypted ``auth_config``, and the
tool runtime calls through it on an agent's behalf. It is governed as a
``connection`` securable, exactly like the database, LLM, and git connections:
all four are credentials pointing at a system outside the platform.

Two problems this module used to have, both fixed here:

* the workspace was read from ``request.state.workspace_id``, which nothing
  sets — ``WorkspaceMiddleware`` sets ``request.state.workspace``. So every
  request ran with ``workspace_id=None``;
* ``svc.get_connection`` looks a connection up by id *or name* and ignores the
  workspace argument entirely, so any id or name resolved from any workspace.

Lookups therefore go through ``authorized_connection`` here rather than through
the service, and the service is only handed an id that has already been
resolved and authorised.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.agents.models.external_connection import ExternalConnection
from app.agents.routes._authz import authorized_connection, visible_connections
from app.agents.schemas.external_connections import (
    ExternalConnectionCreate,
    ExternalConnectionResponse,
    ExternalConnectionUpdate,
)
from app.agents.services import external_connection_service as svc
from app.database import get_system_db as get_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable

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


def _get_or_404(db: Session, connection_id: str, guard: Guard, privilege: Privilege) -> ExternalConnection:
    """Load an external connection the caller holds ``privilege`` on."""
    return authorized_connection(db, guard, ExternalConnection, connection_id, privilege)


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
    guard: Guard = Depends(get_guard),
):
    """Register an external system.

    Admin: ``auth_config`` is a credential for a system CompassX does not
    control, and every agent granted on the connection then calls with it.
    """
    guard.require_workspace_admin("Creating an external connection")
    try:
        conn = svc.create_connection(
            db=db,
            data=payload,
            workspace_id=guard.workspace_id,
            user_id=str(guard.principal.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    guard.claim_ownership(Securable.connection(str(conn.id)))
    return _to_response(conn)


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
    guard: Guard = Depends(get_guard),
):
    """List the external connections the caller may see.

    Queried here rather than through ``svc.list_connections``, which also
    returns rows with a null workspace to every workspace.
    """
    q = db.query(ExternalConnection).filter(
        ExternalConnection.workspace_id == guard.workspace_id
    )
    if status_filter:
        q = q.filter(ExternalConnection.status == status_filter)
    rows = q.order_by(ExternalConnection.created_at.desc()).all()
    return [_to_response(c) for c in visible_connections(guard, rows)]


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
    guard: Guard = Depends(get_guard),
):
    return _to_response(_get_or_404(db, connection_id, guard, Privilege.BROWSE))


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
    guard: Guard = Depends(get_guard),
):
    """Change an external connection.

    EDIT: ``base_url`` decides which host the stored credential is sent to, so
    this can redirect an existing grant at a different system.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    try:
        updated = svc.update_connection(db, conn.id, payload, workspace_id=guard.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _to_response(updated)


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
    guard: Guard = Depends(get_guard),
):
    """Take a connection out of service.

    EDIT rather than MANAGE: it is reversible and nothing is destroyed, but it
    stops every agent using it, so it is not a read.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    try:
        updated = svc.disable_connection(db, conn.id, workspace_id=guard.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _to_response(updated)


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
    guard: Guard = Depends(get_guard),
):
    """Remove a connection and its stored credential.

    MANAGE: irreversible, and it revokes access for everyone granted on it.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.MANAGE)
    db.delete(conn)
    db.commit()
    return None
