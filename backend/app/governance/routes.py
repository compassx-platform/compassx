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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------


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


# ----------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------


@router.get("/privileges")
def list_privileges() -> dict:
    """The privilege vocabulary, for building a grant dialog.

    Served from the backend rather than duplicated in the frontend so the two
    cannot drift into offering privileges the resolver will not honour.
    """
    return {
        "privileges": [p.value for p in Privilege],
        "bundles": {
            name: sorted(p.value for p in privileges)
            for name, privileges in PRIVILEGE_BUNDLES.items()
        },
        "applicable": {
            securable.value: sorted(p.value for p in privileges)
            for securable, privileges in APPLICABLE_PRIVILEGES.items()
        },
    }


# ----------------------------------------------------------------------
# Grants
# ----------------------------------------------------------------------


@router.get("/grants", response_model=list[GrantOut])
def list_grants(
    securable_type: SecurableType,
    name: str,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> list[GrantOut]:
    """Grants made directly on one object — the Permissions tab.

    Requires MANAGE: who holds access to an object is itself sensitive.
    """
    securable = SecurableRef(securable_type=securable_type, name=name).to_securable()
    guard.require(Privilege.MANAGE, securable)
    rows = service.list_grants(db, guard.workspace_id, securable)
    return [_to_grant_out(row) for row in rows]


@router.get("/principals/{principal_id}/grants", response_model=list[GrantOut])
def list_principal_grants(
    principal_id: str,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> list[GrantOut]:
    """Everything one principal holds — the access review for a user or agent.

    Workspace-admin only. A principal may inspect their own access.
    """
    if principal_id != guard.principal.id:
        _require_workspace_admin(guard)
    rows = service.list_principal_grants(db, guard.workspace_id, principal_id)
    return [_to_grant_out(row) for row in rows]


@router.post("/grants", response_model=list[GrantOut], status_code=status.HTTP_201_CREATED)
def create_grant(
    payload: GrantIn,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> list[GrantOut]:
    """Grant privileges. Idempotent — re-granting returns an empty list."""
    securable = payload.to_securable()
    try:
        rows = service.grant(
            db,
            workspace_id=guard.workspace_id,
            securable=securable,
            principal_id=payload.principal_id,
            principal_type=payload.principal_type,
            privileges=payload.privileges,
            actor=guard.principal,
            expires_at=payload.expires_at,
        )
    except PermissionDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except (GovernanceError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return [_to_grant_out(row) for row in rows]


@router.post("/grants/revoke")
def revoke_grant(
    payload: RevokeIn,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> dict:
    """Revoke privileges.

    POST rather than DELETE because the target is a (principal, securable,
    privileges) triple that does not fit a path, and because a DELETE with a
    body is unreliably supported by proxies.
    """
    securable = payload.to_securable()
    try:
        removed = service.revoke(
            db,
            workspace_id=guard.workspace_id,
            securable=securable,
            principal_id=payload.principal_id,
            privileges=payload.privileges,
            actor=guard.principal,
        )
    except PermissionDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except (GovernanceError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return {"revoked": removed}


# ----------------------------------------------------------------------
# Ownership
# ----------------------------------------------------------------------


@router.get("/owner", response_model=OwnerOut | None)
def get_owner(
    securable_type: SecurableType,
    name: str,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> OwnerOut | None:
    """Who owns an object. Visible to anyone who can see the object.

    Deliberately readable at BROWSE: the owner is who you ask for access, so
    hiding it would leave a user who has been denied with nowhere to go.
    """
    securable = SecurableRef(securable_type=securable_type, name=name).to_securable()
    guard.require(Privilege.BROWSE, securable)
    row = service.get_owner(db, guard.workspace_id, securable)
    if row is None:
        return None
    return OwnerOut(
        securable_type=row.securable_type,
        securable_name=securable.full_name,
        owner_principal_id=row.owner_principal_id,
        owner_principal_type=row.owner_principal_type,
        assigned_at=row.assigned_at,
    )


@router.put("/owner", response_model=OwnerOut)
def transfer_owner(
    payload: OwnerIn,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> OwnerOut:
    """Transfer ownership. Requires MANAGE, which an owner holds implicitly."""
    securable = payload.to_securable()
    try:
        row = service.transfer_ownership(
            db,
            workspace_id=guard.workspace_id,
            securable=securable,
            new_owner_principal_id=payload.owner_principal_id,
            new_owner_principal_type=payload.owner_principal_type,
            actor=guard.principal,
        )
    except PermissionDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except (GovernanceError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return OwnerOut(
        securable_type=row.securable_type,
        securable_name=securable.full_name,
        owner_principal_id=row.owner_principal_id,
        owner_principal_type=row.owner_principal_type,
        assigned_at=row.assigned_at,
    )


# ----------------------------------------------------------------------
# Effective permissions
# ----------------------------------------------------------------------


@router.get("/effective", response_model=EffectiveOut)
def effective_permissions(
    securable_type: SecurableType,
    name: str,
    principal_id: str | None = Query(
        default=None,
        description="Defaults to the caller. Inspecting another principal requires workspace admin.",
    ),
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> EffectiveOut:
    """What a principal can actually do here, and why.

    Answers the question an administrator has when access is not behaving as
    expected, without requiring them to reconstruct the resolution order.
    """
    securable = SecurableRef(securable_type=securable_type, name=name).to_securable()

    if principal_id is None or principal_id == guard.principal.id:
        permissions = guard.permissions
        subject = guard.principal
    else:
        _require_workspace_admin(guard)
        subject = Principal(
            id=principal_id,
            workspace_roles={guard.workspace_id: "analyst"},
        )
        permissions = load_permission_set(db, subject, guard.workspace_id)

    applicable = sorted(
        APPLICABLE_PRIVILEGES.get(securable.type, frozenset()),
        key=lambda p: p.value,
    )
    decisions = {p.value: permissions.check(p, securable) for p in applicable}

    owner = service.get_owner(db, guard.workspace_id, securable)
    return EffectiveOut(
        principal_id=subject.id,
        securable_type=securable.type.value,
        securable_name=securable.full_name,
        is_owner=bool(owner and owner.owner_principal_id in subject.all_ids),
        privileges=[name for name, result in decisions.items() if result.allowed],
        decisions={
            name: (f"{result.reason}: {result.detail}" if result.detail else result.reason)
            for name, result in decisions.items()
        },
    )


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


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
