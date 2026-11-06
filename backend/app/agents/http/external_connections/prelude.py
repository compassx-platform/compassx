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
