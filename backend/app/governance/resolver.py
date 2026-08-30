"""Permission resolution — the single place an access decision is made.

No route file re-implements any part of this. Enforcement is uniform because
there is exactly one implementation of ``can``.

Resolution order (deny by default at every branch):

  1. Account admin                     -> allow (break-glass, always audited)
  2. Expand principal set              (user + groups, or agent service identity)
  3. Workspace gate                    (derived from the securable, never from
                                        a client-supplied header)
  4. Ownership                         -> allow
  5. USE chain on ancestors            -> deny if broken
  6. Direct or inherited grant         -> allow
  7. Deny

The principal's full grant set is loaded once per request and evaluated in
memory. Listing a catalog with 10,000 tables must not issue 10,000 queries;
see ``PermissionSet.filter_visible``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.governance.models import AgentPrincipal, ObjectGrant, SecurableOwner
from app.governance.privileges import (
    Privilege,
    SecurableType,
    expand_bundle,
    implied_by_manage,
)
from app.governance.securable import WORKSPACE_SENTINEL, Securable

logger = logging.getLogger(__name__)


class Decision:
    """Why access was allowed or denied. Recorded in the audit log."""

    ACCOUNT_ADMIN = "account_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    OWNER = "owner"
    DIRECT_GRANT = "direct_grant"
    INHERITED_GRANT = "inherited_grant"
    NO_WORKSPACE_ACCESS = "no_workspace_access"
    USE_CHAIN_BROKEN = "use_chain_broken"
    AGENT_CEILING = "agent_ceiling_exceeded"
    NO_GRANT = "no_grant"


@dataclass(frozen=True, slots=True)
class AccessResult:
    allowed: bool
    reason: str
    #: For a denial caused by a broken USE chain, the ancestor that failed.
    detail: str | None = None

    def __bool__(self) -> bool:
        return self.allowed


@dataclass(slots=True)
class Principal:
    """The identity an access decision is made for.

    ``group_ids`` is pre-expanded so resolution does no further identity
    lookups. ``on_behalf_of`` is set when an agent service identity is acting
    for a user, and is carried into the audit log.
    """

    id: str
    type: str = "user"  # user | group | service
    is_account_admin: bool = False
    group_ids: tuple[str, ...] = ()
    workspace_roles: dict[str, str] = field(default_factory=dict)
    on_behalf_of: str | None = None

    @property
    def all_ids(self) -> tuple[str, ...]:
        """Every principal id whose grants apply to this identity."""
        return (self.id, *self.group_ids)

    def workspace_role(self, workspace_id: str) -> str | None:
        return self.workspace_roles.get(workspace_id)


@dataclass(slots=True)
class _Grant:
    """An in-memory grant, with its securable and expanded privileges."""

    securable: Securable
    privileges: frozenset[Privilege]


class PermissionSet:
    """A principal's grants within one workspace, loaded once and reused.

    Constructing this per request and passing it down is what keeps list
    endpoints to a constant number of queries.
    """

    def __init__(
        self,
        principal: Principal,
        workspace_id: str,
        grants: Sequence[_Grant],
        owned: frozenset[tuple[str, str, str | None, str | None]],
    ) -> None:
        self.principal = principal
        self.workspace_id = workspace_id
        self._grants = list(grants)
        self._owned = owned

    # ------------------------------------------------------------------
    # Core decision
    # ------------------------------------------------------------------

    def check(self, privilege: Privilege, securable: Securable) -> AccessResult:
        """Evaluate one privilege against one securable."""
        # 1. Account admin break-glass.
        if self.principal.is_account_admin:
            return AccessResult(True, Decision.ACCOUNT_ADMIN)

        # 3. Workspace gate. The workspace comes from the securable's
        #    resolved context, never from a request header.
        ws_role = self.principal.workspace_role(self.workspace_id)
        if ws_role is None:
            return AccessResult(False, Decision.NO_WORKSPACE_ACCESS)
        if ws_role == "workspace_admin":
            return AccessResult(True, Decision.WORKSPACE_ADMIN)

        # 4. Ownership implies MANAGE, which implies everything applicable.
        if self._is_owner(securable):
            if privilege in implied_by_manage(securable.type):
                return AccessResult(True, Decision.OWNER)

        # 5. USE chain: every ancestor container must be traversable.
        #    Checked before grants so that a broken chain is reported as such
        #    rather than as a missing grant — the distinction matters when an
        #    administrator is debugging why access failed.
        for ancestor in securable.ancestors():
            if not self._has_privilege(Privilege.USE, ancestor):
                return AccessResult(
                    False, Decision.USE_CHAIN_BROKEN, detail=ancestor.full_name
                )

        # 6. Direct or inherited grant.
        if self._is_owner(securable):
            # Owner of the object but the privilege is not applicable to it.
            return AccessResult(False, Decision.NO_GRANT)
        match = self._matching_grant(privilege, securable)
        if match is not None:
            reason = (
                Decision.DIRECT_GRANT
                if match.securable == securable
                else Decision.INHERITED_GRANT
            )
            return AccessResult(True, reason, detail=match.securable.full_name)

        # 7. Deny.
        return AccessResult(False, Decision.NO_GRANT)

    def can(self, privilege: Privilege, securable: Securable) -> bool:
        return self.check(privilege, securable).allowed

    # ------------------------------------------------------------------
    # List filtering
    # ------------------------------------------------------------------

    def filter_visible(
        self, privilege: Privilege, securables: Iterable[Securable]
    ) -> list[Securable]:
        """Return only the securables the principal may access.

        List endpoints filter; they never raise 403. A user with access to
        three of five hundred tables sees three tables.
        """
        return [s for s in securables if self.can(privilege, s)]

    def accessible_catalog_prefixes(
        self, privilege: Privilege
    ) -> list[tuple[str, str | None]]:
        """(catalog, schema) prefixes the principal holds ``privilege`` on.

        Lets callers push filtering into SQL for large result sets instead of
        materialising every row and discarding most of it.
        """
        prefixes: set[tuple[str, str | None]] = set()
        for grant in self._grants:
            if not grant.securable.is_catalog_path:
                continue
            if privilege not in grant.privileges and Privilege.MANAGE not in grant.privileges:
                continue
            prefixes.add((grant.securable.catalog, grant.securable.schema))  # type: ignore[arg-type]
        return sorted(prefixes, key=lambda p: (p[0], p[1] or ""))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_owner(self, securable: Securable) -> bool:
        key = (
            securable.type.value,
            securable.storage_catalog,
            securable.schema,
            securable.asset,
        )
        return key in self._owned

    def _has_privilege(self, privilege: Privilege, securable: Securable) -> bool:
        if self._is_owner(securable) and privilege in implied_by_manage(securable.type):
            return True
        return self._matching_grant(privilege, securable) is not None

    def _matching_grant(
        self, privilege: Privilege, securable: Securable
    ) -> _Grant | None:
        for grant in self._grants:
            if not grant.securable.covers(securable):
                continue
            if privilege in grant.privileges or Privilege.MANAGE in grant.privileges:
                return grant
        return None


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------


def load_permission_set(
    db: Session, principal: Principal, workspace_id: str
) -> PermissionSet:
    """Load every grant and ownership record for a principal in one workspace.

    Two queries regardless of how many objects will subsequently be checked.
    """
    principal_ids = list(principal.all_ids)
    now = datetime.now(timezone.utc)

    grant_rows = db.execute(
        select(ObjectGrant).where(
            ObjectGrant.workspace_id == workspace_id,
            ObjectGrant.principal_id.in_(principal_ids),
            or_(ObjectGrant.expires_at.is_(None), ObjectGrant.expires_at > now),
        )
    ).scalars().all()

    grants = [g for g in (_to_grant(row) for row in grant_rows) if g is not None]

    owner_rows = db.execute(
        select(
            SecurableOwner.securable_type,
            SecurableOwner.catalog_name,
            SecurableOwner.schema_name,
            SecurableOwner.asset_name,
        ).where(
            SecurableOwner.workspace_id == workspace_id,
            SecurableOwner.owner_principal_id.in_(principal_ids),
        )
    ).all()
    owned = frozenset(
        (row.securable_type, row.catalog_name, row.schema_name, row.asset_name)
        for row in owner_rows
    )

    return PermissionSet(principal, workspace_id, grants, owned)


def load_agent_permission_set(
    db: Session,
    agent_id: str,
    invoking_user: Principal,
    workspace_id: str,
) -> PermissionSet:
    """Load an agent's effective permissions, capped by its owner's.

    Agents hold their own grants (owner decision, 2026-08-29). The ceiling rule
    is what keeps that safe: an agent's effective access is the intersection of
    its own grants with its owner's. An agent can therefore never exceed the
    person responsible for it, and loses access the moment its owner does.

    Without this, "grant a user EXECUTE on an agent" would silently become
    "grant that user everything the agent can reach" — a confused-deputy
    escalation, made worse by prompt injection.
    """
    agent_row = db.execute(
        select(AgentPrincipal).where(
            AgentPrincipal.agent_id == agent_id,
            AgentPrincipal.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if agent_row is None:
        # No service identity provisioned: the agent has no standing access.
        empty = PermissionSet(
            Principal(id=agent_id, type="service", on_behalf_of=invoking_user.id),
            workspace_id,
            [],
            frozenset(),
        )
        return empty

    agent_principal = Principal(
        id=agent_row.principal_id,
        type="service",
        is_account_admin=False,
        workspace_roles={workspace_id: "analyst"},
        on_behalf_of=invoking_user.id,
    )
    agent_set = load_permission_set(db, agent_principal, workspace_id)

    owner_principal = Principal(
        id=agent_row.owner_principal_id,
        type=agent_row.owner_principal_type,
        workspace_roles={workspace_id: "analyst"},
    )
    owner_set = load_permission_set(db, owner_principal, workspace_id)

    return _CappedPermissionSet(agent_set, owner_set)


class _CappedPermissionSet(PermissionSet):
    """An agent's permissions intersected with its owner's ceiling."""

    def __init__(self, agent_set: PermissionSet, owner_set: PermissionSet) -> None:
        super().__init__(
            agent_set.principal,
            agent_set.workspace_id,
            agent_set._grants,
            agent_set._owned,
        )
        self._owner_set = owner_set

    def check(self, privilege: Privilege, securable: Securable) -> AccessResult:
        own = super().check(privilege, securable)
        if not own.allowed:
            return own
        ceiling = self._owner_set.check(privilege, securable)
        if not ceiling.allowed:
            return AccessResult(False, Decision.AGENT_CEILING, detail=securable.full_name)
        return own


def _to_grant(row: ObjectGrant) -> _Grant | None:
    """Convert a stored row into an evaluable grant.

    A row that cannot be interpreted is skipped rather than raising, so one bad
    record cannot deny all access for a principal. It is logged loudly because
    a grant that exists but does nothing is exactly the kind of silent failure
    that erodes trust in a permission system.
    """
    try:
        securable_type = SecurableType(row.securable_type)
    except ValueError:
        logger.error(
            "Skipping grant %s: unknown securable_type %r", row.id, row.securable_type
        )
        return None

    try:
        if securable_type in (SecurableType.CATALOG, SecurableType.SCHEMA) or (
            row.catalog_name != WORKSPACE_SENTINEL
        ):
            securable = Securable(
                type=securable_type,
                catalog=row.catalog_name,
                schema=row.schema_name,
                asset=row.asset_name,
            )
        else:
            securable = Securable(type=securable_type, asset=row.asset_name)
    except ValueError as exc:
        logger.error("Skipping malformed grant %s: %s", row.id, exc)
        return None

    source = row.privilege or row.object_role_id
    if not source:
        logger.error("Skipping grant %s: neither privilege nor object_role_id set", row.id)
        return None

    try:
        privileges = expand_bundle(source)
    except ValueError as exc:
        logger.error("Skipping grant %s: %s", row.id, exc)
        return None

    return _Grant(securable=securable, privileges=privileges)
