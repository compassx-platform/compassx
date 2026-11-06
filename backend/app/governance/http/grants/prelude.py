"""Governance API — grants, ownership, and effective-permission inspection.

Routes are workspace-scoped and mounted under ``/api/v1/governance``. Every
mutation goes through ``app.governance.service`` so that validation, the MANAGE
requirement, the agent ceiling, and audit cannot be bypassed here.

The read endpoints matter as much as the write ones: most access problems are
diagnosed rather than granted, and ``/effective`` answers the question an
administrator actually has — "why can this person not open this table?" —
without them having to reconstruct the resolution order by hand.
"""

from __future__ import annotations

import logging

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.database import get_system_db

from app.governance import service

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import (
    APPLICABLE_PRIVILEGES,
    PRIVILEGE_BUNDLES,
    WORKSPACE_SECURABLES,
    Privilege,
    SecurableType,
)

from app.governance.resolver import Principal, load_permission_set

from app.governance.securable import Securable

from app.governance.service import GovernanceError, PermissionDenied

logger = logging.getLogger("app.governance.routes")

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])

class SecurableRef(BaseModel):
    """How the API addresses a governed object."""

    securable_type: SecurableType
    #: Dotted path (``main.sales.orders``) for catalog-path securables;
    #: the object id for jobs, agents, compute, and connections.
    name: str = Field(min_length=1)

    def to_securable(self) -> Securable:
        try:
            return Securable.parse(self.securable_type, self.name)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None

class GrantIn(SecurableRef):
    principal_id: str
    principal_type: str = Field(default="user", pattern="^(user|group|service)$")
    #: Privilege names and/or bundle names, mixed freely.
    privileges: list[str] = Field(min_length=1)
    #: Null means the grant does not expire.
    expires_at: datetime | None = None

class RevokeIn(SecurableRef):
    principal_id: str
    privileges: list[str] = Field(min_length=1)

class GrantOut(BaseModel):
    id: str
    principal_id: str
    principal_type: str
    securable_type: str
    securable_name: str
    privilege: str | None
    granted_by: str | None
    granted_at: datetime
    expires_at: datetime | None

class OwnerIn(SecurableRef):
    owner_principal_id: str
    owner_principal_type: str = Field(default="user", pattern="^(user|group)$")

class OwnerOut(BaseModel):
    securable_type: str
    securable_name: str
    owner_principal_id: str
    owner_principal_type: str
    assigned_at: datetime

class EffectiveOut(BaseModel):
    """Why a principal can or cannot do something — the debugging endpoint."""

    principal_id: str
    securable_type: str
    securable_name: str
    is_owner: bool
    #: Privileges the principal actually holds here, after the USE chain.
    privileges: list[str]
    #: Per-privilege resolution reason, including for denials.
    decisions: dict[str, str]

def _require_workspace_admin(guard: Guard) -> None:
    if guard.principal.is_account_admin:
        return
    if guard.principal.workspace_role(guard.workspace_id) == "workspace_admin":
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Workspace admin is required to inspect another principal's access.",
    )

def _to_grant_out(row) -> GrantOut:
    kind = SecurableType(row.securable_type)
    if kind in WORKSPACE_SECURABLES:
        securable = Securable(kind, asset=row.asset_name)
    else:
        securable = Securable(
            kind,
            catalog=row.catalog_name,
            schema=row.schema_name,
            asset=row.asset_name,
        )
    return GrantOut(
        id=row.id,
        principal_id=row.principal_id,
        principal_type=row.principal_type,
        securable_type=row.securable_type,
        securable_name=securable.full_name,
        privilege=row.privilege or row.object_role_id,
        granted_by=row.granted_by,
        granted_at=row.granted_at,
        expires_at=row.expires_at,
    )
