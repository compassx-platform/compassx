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

logger = logging.getLogger("app.agents.routes.external_connection_routes")

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

import app.agents.http.external_connections.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.external_connections.application.create_external_connection import create_external_connection as create_external_connection_action
from app.agents.http.external_connections.application.list_external_connections import list_external_connections as list_external_connections_action
from app.agents.http.external_connections.application.get_external_connection import get_external_connection as get_external_connection_action
from app.agents.http.external_connections.application.update_external_connection import update_external_connection as update_external_connection_action
from app.agents.http.external_connections.application.disable_external_connection import disable_external_connection as disable_external_connection_action
from app.agents.http.external_connections.application.delete_external_connection import delete_external_connection as delete_external_connection_action

logger = logging.getLogger("app.agents.routes.external_connection_routes")

router = APIRouter(tags=["External Connections"])

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
    return create_external_connection_action(payload=payload, request=request, db=db, guard=guard)

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
    return list_external_connections_action(request=request, status_filter=status_filter, db=db, guard=guard)

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
    return get_external_connection_action(connection_id=connection_id, request=request, db=db, guard=guard)

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
    return update_external_connection_action(connection_id=connection_id, payload=payload, request=request, db=db, guard=guard)

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
    return disable_external_connection_action(connection_id=connection_id, request=request, db=db, guard=guard)

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
    return delete_external_connection_action(connection_id=connection_id, request=request, db=db, guard=guard)
