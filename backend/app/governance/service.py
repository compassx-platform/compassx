"""Grant administration — the write side of governance.

Everything that changes who can do what goes through here, so that validation
and audit cannot be bypassed by a route taking a shortcut.

Rules enforced at this boundary:
  * A privilege must be applicable to the securable type (no SELECT on a job).
  * The granter must hold MANAGE on the securable — you cannot give away access
    you do not administer.
  * An agent may not be granted a privilege its owner does not hold (the
    ceiling rule; the resolver also enforces this at evaluation time, but
    catching it at grant time gives the administrator an immediate error
    rather than a grant that silently never applies).
  * Every mutation writes an audit record.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.governance.models import (
    AccessAuditLog,
    AgentPrincipal,
    ObjectGrant,
    SecurableOwner,
)
from app.governance.privileges import (
    Privilege,
    SecurableType,
    expand_bundle,
    validate_privilege_for_securable,
)
from app.governance.resolver import (
    Principal,
    load_permission_set,
)
from app.governance.securable import Securable

logger = logging.getLogger(__name__)


class GovernanceError(Exception):
    """Raised when a grant operation is invalid. Mapped to 400/403 by routes."""


class PermissionDenied(GovernanceError):
    """The actor may not perform this administration action."""


# ----------------------------------------------------------------------
# Ownership
# ----------------------------------------------------------------------


def set_owner(
    db: Session,
    *,
    workspace_id: str,
    securable: Securable,
    owner_principal_id: str,
    owner_principal_type: str = "user",
    actor: Principal | None = None,
    commit: bool = True,
) -> SecurableOwner:
    """Assign or replace ownership of a securable.

    Called at object-creation time (creator becomes owner) and on explicit
    ownership transfer. There is no unowned state.
    """
    existing = _owner_row(db, workspace_id, securable)

    if existing is not None:
        existing.owner_principal_id = owner_principal_id
        existing.owner_principal_type = owner_principal_type
        existing.assigned_by = actor.id if actor else None
        row = existing
    else:
        row = SecurableOwner(
            workspace_id=workspace_id,
            securable_type=securable.type.value,
            catalog_name=securable.storage_catalog,
            schema_name=securable.schema,
            asset_name=securable.asset,
            owner_principal_id=owner_principal_id,
            owner_principal_type=owner_principal_type,
            assigned_by=actor.id if actor else None,
        )
        db.add(row)

    _audit(
        db,
        workspace_id=workspace_id,
        event_type="transfer_ownership",
        actor=actor,
        securable=securable,
        reason=f"owner set to {owner_principal_type}:{owner_principal_id}",
    )
    if commit:
        db.commit()
    return row


def transfer_ownership(
    db: Session,
    *,
    workspace_id: str,
    securable: Securable,
    new_owner_principal_id: str,
    new_owner_principal_type: str,
    actor: Principal,
) -> SecurableOwner:
    """Transfer ownership. Requires MANAGE on the securable."""
    _require_manage(db, actor, workspace_id, securable)
    return set_owner(
        db,
        workspace_id=workspace_id,
        securable=securable,
        owner_principal_id=new_owner_principal_id,
        owner_principal_type=new_owner_principal_type,
        actor=actor,
    )


def get_owner(
    db: Session, workspace_id: str, securable: Securable
) -> SecurableOwner | None:
    return _owner_row(db, workspace_id, securable)


def relocate(
    db: Session,
    *,
    workspace_id: str,
    old: Securable,
    new: Securable,
    actor: Principal | None = None,
    commit: bool = True,
) -> None:
    """Follow an object's grants and ownership when it is renamed or moved.

    Grants address objects by path, so without this a rename silently revokes
    everyone — the grants would still exist, pointing at a name nothing
    answers to. That failure is invisible: the Permissions tab still lists
    them, and only the users notice.

    Grants made on the *old container* are deliberately not copied. Those were
    a statement about the schema, not about this object, and the object is no
    longer in that schema.
    """
    if old == new:
        return

    for row in db.execute(
        select(ObjectGrant).where(
            ObjectGrant.workspace_id == workspace_id,
            ObjectGrant.securable_type == old.type.value,
            ObjectGrant.catalog_name == old.storage_catalog,
            _null_safe(ObjectGrant.schema_name, old.schema),
            _null_safe(ObjectGrant.asset_name, old.asset),
        )
    ).scalars().all():
        row.securable_type = new.type.value
        row.catalog_name = new.storage_catalog
        row.schema_name = new.schema
        row.asset_name = new.asset

    owner = _owner_row(db, workspace_id, old)
    if owner is not None:
        owner.securable_type = new.type.value
        owner.catalog_name = new.storage_catalog
        owner.schema_name = new.schema
        owner.asset_name = new.asset

    _audit(
        db,
        workspace_id=workspace_id,
        event_type="relocate",
        actor=actor,
        securable=new,
        reason=f"moved from {old.full_name}",
    )
    if commit:
        db.commit()


# ----------------------------------------------------------------------
# Grant / revoke
# ----------------------------------------------------------------------


def grant(
    db: Session,
    *,
    workspace_id: str,
    securable: Securable,
    principal_id: str,
    principal_type: str,
    privileges: Sequence[str],
    actor: Principal,
    expires_at: datetime | None = None,
) -> list[ObjectGrant]:
    """Grant one or more privileges (or a bundle) on a securable.

    ``privileges`` accepts raw privilege names and bundle names
    interchangeably; bundles are expanded and stored as individual privilege
    rows so that a later revoke can be precise.
    """
    _require_manage(db, actor, workspace_id, securable)

    resolved: set[Privilege] = set()
    for name in privileges:
        resolved |= expand_bundle(name)

    # Reject grants that could never be evaluated, so an administrator gets an
    # error instead of a row that looks like access but confers none.
    applicable: set[Privilege] = set()
    for privilege in resolved:
        try:
            validate_privilege_for_securable(privilege, securable.type)
        except ValueError:
            # Bundles intentionally span securable types (a "viewer" bundle
            # includes USE, which is meaningless on a table). Silently drop
            # inapplicable members of a bundle, but reject an explicitly named
            # privilege that does not apply.
            if len(privileges) == 1 and privileges[0].upper() == privilege.value:
                raise
            continue
        applicable.add(privilege)

    if not applicable:
        raise GovernanceError(
            f"None of {list(privileges)} are applicable to {securable.type.value}."
        )

    if principal_type == "service":
        _check_agent_ceiling(db, workspace_id, principal_id, applicable, securable)

    created: list[ObjectGrant] = []
    for privilege in sorted(applicable, key=lambda p: p.value):
        if _grant_row(db, workspace_id, securable, principal_id, privilege) is not None:
            continue  # already granted; grant is idempotent
        row = ObjectGrant(
            workspace_id=workspace_id,
            principal_id=principal_id,
            principal_type=principal_type,
            securable_type=securable.type.value,
            catalog_name=securable.storage_catalog,
            schema_name=securable.schema,
            asset_name=securable.asset,
            privilege=privilege.value,
            granted_by=actor.id,
            expires_at=expires_at,
        )
        db.add(row)
        created.append(row)
        _audit(
            db,
            workspace_id=workspace_id,
            event_type="grant",
            actor=actor,
            securable=securable,
            privilege=privilege,
            target_principal_id=principal_id,
            reason=f"granted to {principal_type}:{principal_id}",
        )

    db.commit()
    return created


def revoke(
    db: Session,
    *,
    workspace_id: str,
    securable: Securable,
    principal_id: str,
    privileges: Sequence[str],
    actor: Principal,
) -> int:
    """Revoke privileges. Returns the number of grant rows removed."""
    _require_manage(db, actor, workspace_id, securable)

    resolved: set[Privilege] = set()
    for name in privileges:
        resolved |= expand_bundle(name)

    result = db.execute(
        delete(ObjectGrant).where(
            ObjectGrant.workspace_id == workspace_id,
            ObjectGrant.principal_id == principal_id,
            ObjectGrant.securable_type == securable.type.value,
            ObjectGrant.catalog_name == securable.storage_catalog,
            _null_safe(ObjectGrant.schema_name, securable.schema),
            _null_safe(ObjectGrant.asset_name, securable.asset),
            ObjectGrant.privilege.in_([p.value for p in resolved]),
        )
    )

    for privilege in sorted(resolved, key=lambda p: p.value):
        _audit(
            db,
            workspace_id=workspace_id,
            event_type="revoke",
            actor=actor,
            securable=securable,
            privilege=privilege,
            target_principal_id=principal_id,
            reason=f"revoked from {principal_id}",
        )

    db.commit()
    return result.rowcount or 0


def list_grants(
    db: Session, workspace_id: str, securable: Securable
) -> list[ObjectGrant]:
    """Grants made directly on a securable — powers the Permissions tab."""
    return list(
        db.execute(
            select(ObjectGrant).where(
                ObjectGrant.workspace_id == workspace_id,
                ObjectGrant.securable_type == securable.type.value,
                ObjectGrant.catalog_name == securable.storage_catalog,
                _null_safe(ObjectGrant.schema_name, securable.schema),
                _null_safe(ObjectGrant.asset_name, securable.asset),
            )
        ).scalars().all()
    )


def list_principal_grants(
    db: Session, workspace_id: str, principal_id: str
) -> list[ObjectGrant]:
    """Every grant held by one principal — powers the agent access review."""
    return list(
        db.execute(
            select(ObjectGrant).where(
                ObjectGrant.workspace_id == workspace_id,
                ObjectGrant.principal_id == principal_id,
            )
        ).scalars().all()
    )


# ----------------------------------------------------------------------
# Agent service identities
# ----------------------------------------------------------------------


def ensure_agent_principal(
    db: Session,
    *,
    agent_id: str,
    workspace_id: str,
    owner_principal_id: str,
    owner_principal_type: str = "user",
    commit: bool = True,
) -> AgentPrincipal:
    """Create the service identity an agent holds grants under.

    The owner is the ceiling for everything the agent can ever do, so this is
    a security-relevant field, not provenance.
    """
    existing = db.execute(
        select(AgentPrincipal).where(AgentPrincipal.agent_id == agent_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    row = AgentPrincipal(
        agent_id=agent_id,
        workspace_id=workspace_id,
        owner_principal_id=owner_principal_id,
        owner_principal_type=owner_principal_type,
    )
    db.add(row)
    if commit:
        db.commit()
    return row


def get_agent_principal(db: Session, agent_id: str) -> AgentPrincipal | None:
    return db.execute(
        select(AgentPrincipal).where(AgentPrincipal.agent_id == agent_id)
    ).scalar_one_or_none()


def _check_agent_ceiling(
    db: Session,
    workspace_id: str,
    agent_principal_id: str,
    privileges: set[Privilege],
    securable: Securable,
) -> None:
    """Reject granting an agent more than its owner holds.

    Enforced here as well as in the resolver so the administrator sees an
    immediate, explicable error rather than creating a grant that will be
    silently capped at evaluation time.
    """
    agent_row = db.execute(
        select(AgentPrincipal).where(AgentPrincipal.principal_id == agent_principal_id)
    ).scalar_one_or_none()
    if agent_row is None:
        return  # not an agent identity we manage

    owner = Principal(
        id=agent_row.owner_principal_id,
        type=agent_row.owner_principal_type,
        workspace_roles={workspace_id: "analyst"},
    )
    owner_set = load_permission_set(db, owner, workspace_id)

    for privilege in sorted(privileges, key=lambda p: p.value):
        if not owner_set.can(privilege, securable):
            raise GovernanceError(
                f"Cannot grant {privilege.value} on {securable.full_name} to this agent: "
                f"its owner does not hold that privilege. An agent may never exceed "
                f"the access of the principal responsible for it."
            )


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _require_manage(
    db: Session, actor: Principal, workspace_id: str, securable: Securable
) -> None:
    """You cannot give away access you do not administer."""
    permissions = load_permission_set(db, actor, workspace_id)
    if not permissions.can(Privilege.MANAGE, securable):
        raise PermissionDenied(
            f"MANAGE on {securable.full_name} is required to change its permissions."
        )


def _owner_row(
    db: Session, workspace_id: str, securable: Securable
) -> SecurableOwner | None:
    return db.execute(
        select(SecurableOwner).where(
            SecurableOwner.workspace_id == workspace_id,
            SecurableOwner.securable_type == securable.type.value,
            SecurableOwner.catalog_name == securable.storage_catalog,
            _null_safe(SecurableOwner.schema_name, securable.schema),
            _null_safe(SecurableOwner.asset_name, securable.asset),
        )
    ).scalar_one_or_none()


def _grant_row(
    db: Session,
    workspace_id: str,
    securable: Securable,
    principal_id: str,
    privilege: Privilege,
) -> ObjectGrant | None:
    return db.execute(
        select(ObjectGrant).where(
            ObjectGrant.workspace_id == workspace_id,
            ObjectGrant.principal_id == principal_id,
            ObjectGrant.securable_type == securable.type.value,
            ObjectGrant.catalog_name == securable.storage_catalog,
            _null_safe(ObjectGrant.schema_name, securable.schema),
            _null_safe(ObjectGrant.asset_name, securable.asset),
            ObjectGrant.privilege == privilege.value,
        )
    ).scalar_one_or_none()


def _null_safe(column, value):
    """``column == None`` does not match NULL in SQL; use IS NULL."""
    return column.is_(None) if value is None else column == value


def _audit(
    db: Session,
    *,
    workspace_id: str | None,
    event_type: str,
    actor: Principal | None,
    securable: Securable | None = None,
    privilege: Privilege | None = None,
    decision: str | None = None,
    reason: str | None = None,
    target_principal_id: str | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            workspace_id=workspace_id,
            event_type=event_type,
            principal_id=actor.id if actor else target_principal_id,
            principal_type=actor.type if actor else None,
            on_behalf_of_principal_id=actor.on_behalf_of if actor else None,
            securable_type=securable.type.value if securable else None,
            securable_name=securable.full_name if securable else None,
            privilege=privilege.value if privilege else None,
            decision=decision,
            reason=reason,
        )
    )


def record_access_decision(
    db: Session,
    *,
    workspace_id: str | None,
    principal: Principal,
    securable: Securable,
    privilege: Privilege,
    allowed: bool,
    reason: str,
) -> None:
    """Audit an authorization decision.

    Denials are recorded alongside allows: an access review needs to see
    attempted access, not only successful access.
    """
    _audit(
        db,
        workspace_id=workspace_id,
        event_type="access",
        actor=principal,
        securable=securable,
        privilege=privilege,
        decision="allow" if allowed else "deny",
        reason=reason,
    )
