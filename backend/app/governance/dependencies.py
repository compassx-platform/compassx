"""Enforcement — the only place a route asks "may this principal do this?".

Two entry points, because endpoints come in two shapes:

  * ``require(privilege, securable_from=...)`` — a route-level dependency, for
    handlers whose securable is fully determined by path parameters.
    ::

        @router.get(
            "/catalogs/{catalog}/schemas/{schema}/tables/{table}",
            dependencies=[Depends(require(
                Privilege.SELECT,
                lambda p: Securable.table(p["catalog"], p["schema"], p["table"]),
            ))],
        )

  * ``Guard`` — injected and called inside the handler, for the (common) case
    where the securable is only known after a lookup, and for list endpoints
    which filter rather than refuse.
    ::

        def list_tables(guard: Guard = Depends(get_guard)):
            return guard.filter(Privilege.BROWSE, candidates)

Neither re-implements any part of the decision; both delegate to the resolver.

Status codes
------------
A principal who cannot even BROWSE an object gets **404**, not 403. Returning
403 would confirm the object exists, which turns an unauthorized user into an
enumeration oracle for table and job names. 403 is reserved for "you can see
this, but not do that to it" — which is actionable, because the user knows
what to request access to.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable, Sequence, TypeVar

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_account_db, get_system_db
from app.governance.privileges import Privilege
from app.governance.resolver import (
    Decision,
    PermissionSet,
    Principal,
    load_agent_permission_set,
    load_permission_set,
)
from app.governance.securable import Securable

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Privileges whose successful use is worth an audit row. Denials are always
#: audited; auditing every allowed read as well would make the log mostly
#: noise and hide the events an access review is actually looking for.
_AUDITED_ON_ALLOW: frozenset[Privilege] = frozenset({
    Privilege.MODIFY,
    Privilege.CREATE,
    Privilege.EDIT,
    Privilege.EXECUTE,
    Privilege.MANAGE,
})


# ----------------------------------------------------------------------
# Principal construction
# ----------------------------------------------------------------------


def get_principal(
    request: Request,
    account_db: Session = Depends(get_account_db),
) -> Principal:
    """Build the identity an access decision will be made for.

    Group membership is expanded once here so that resolution itself performs
    no identity lookups.
    """
    cached = getattr(request.state, "governance_principal", None)
    if cached is not None:
        return cached

    ctx = getattr(request.state, "workspace", None)
    if ctx is None:
        try:
            from app.workspace.middleware import (
                _extract_token,
                resolve_workspace_context,
                _get_default_workspace_slug_for_token,
            )
            token = _extract_token(request)
            slug = (
                request.headers.get("x-workspace-slug")
                or request.query_params.get("workspace")
                or request.query_params.get("workspace_id")
            )
            if not slug and token:
                slug = _get_default_workspace_slug_for_token(token)
            if slug and token:
                ctx = resolve_workspace_context(slug, token)
                request.state.workspace = ctx
        except Exception:
            pass

    if ctx is None:
        # Identity and workspace role are established together by the
        # workspace middleware. Deriving a principal without them would mean
        # guessing at the workspace gate, so refuse instead.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated for a workspace",
        )

    user_id = str(ctx.principal_id)
    principal = Principal(
        id=user_id,
        type="user",
        is_account_admin=ctx.is_account_admin,
        group_ids=_group_ids(account_db, user_id),
        workspace_roles={str(ctx.workspace_id): ctx.principal_role},
    )
    request.state.governance_principal = principal
    return principal


def _group_ids(account_db: Session, user_id: str) -> tuple[str, ...]:
    from app.user_manager.models.account_models import UmGroupMember

    try:
        rows = (
            account_db.query(UmGroupMember.group_id)
            .filter(UmGroupMember.user_id == user_id)
            .all()
        )
    except Exception:  # pragma: no cover - identity store unavailable
        # Failing closed on group expansion would lock out every user whose
        # access is granted via a group. Log and continue with direct grants
        # only; the decision still defaults to deny.
        logger.exception("Group expansion failed for principal %s", user_id)
        return ()
    return tuple(str(row[0]) for row in rows)


def current_workspace_id(request: Request) -> str:
    """The workspace an access decision is scoped to.

    Read from the resolved workspace context, never from a client-supplied
    body or query parameter — otherwise a caller could pick the workspace in
    which they happen to hold a grant.
    """
    ctx = getattr(request.state, "workspace", None)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace context. Address this endpoint under /w/<workspace>.",
        )
    return str(ctx.workspace_id)


# ----------------------------------------------------------------------
# Guard
# ----------------------------------------------------------------------


class Guard:
    """A request-scoped permission set with HTTP semantics attached.

    Loaded once per request; every subsequent check is evaluated in memory, so
    a handler may check a thousand objects without issuing a thousand queries.
    """

    def __init__(
        self,
        permissions: PermissionSet,
        db: Session,
        principal: Principal,
        workspace_id: str,
    ) -> None:
        self.permissions = permissions
        self.principal = principal
        self.workspace_id = workspace_id
        self._db = db

    # -- decisions ------------------------------------------------------

    def can(self, privilege: Privilege, securable: Securable) -> bool:
        """Non-raising check, for shaping a response (hiding a button, etc.)."""
        return self.permissions.can(privilege, securable)

    def require(self, privilege: Privilege, securable: Securable) -> None:
        """Raise 403/404 unless the principal holds ``privilege``."""
        result = self.permissions.check(privilege, securable)
        self._audit(privilege, securable, result.allowed, result.reason)
        if result.allowed:
            return
        raise self._error(privilege, securable, result.reason, result.detail)

    def filter(
        self,
        privilege: Privilege,
        items: Iterable[T],
        securable_of: Callable[[T], Securable] | None = None,
    ) -> list[T]:
        """Return only the items the principal may access.

        List endpoints filter; they never refuse. A user with access to three
        of five hundred tables sees three tables, not an error.
        """
        to_securable = securable_of or (lambda item: item)  # type: ignore[return-value]
        return [item for item in items if self.can(privilege, to_securable(item))]

    def visible_prefixes(self, privilege: Privilege) -> list[tuple[str, str | None]]:
        """(catalog, schema) prefixes for pushing filtering down into SQL."""
        return self.permissions.accessible_catalog_prefixes(privilege)

    def require_workspace_admin(self, action: str) -> None:
        """Gate an action that has no securable to grant on.

        Creating a catalog, or a maintenance sweep across every object, cannot
        be expressed as a privilege on a thing — the thing does not exist yet,
        or the action spans all of them. Those sit with the workspace admin
        rather than becoming implicitly public.
        """
        if self.principal.is_account_admin:
            return
        if self.principal.workspace_role(self.workspace_id) == "workspace_admin":
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{action} requires workspace administrator.",
        )

    # -- ownership ------------------------------------------------------

    def claim_ownership(self, securable: Securable) -> None:
        """Make the caller the owner of an object they just created.

        Every object gets an owner at birth. Without this a newly created
        table would be reachable only by admins, and — worse — would have
        nobody to ask for access.
        """
        from app.governance.service import set_owner

        set_owner(
            self._db,
            workspace_id=self.workspace_id,
            securable=securable,
            owner_principal_id=self.principal.id,
            owner_principal_type="user",
            actor=self.principal,
        )

    def relocate(self, old: Securable, new: Securable) -> None:
        """Carry grants and ownership across a rename or move.

        Call this on every path that changes an object's name or container.
        Grants address objects by path; skipping this silently revokes
        everyone while leaving the grants visible in the UI.
        """
        from app.governance.service import relocate

        relocate(
            self._db,
            workspace_id=self.workspace_id,
            old=old,
            new=new,
            actor=self.principal,
        )

    # -- agent identity -------------------------------------------------

    def as_agent(self, agent_id: str) -> "Guard":
        """A guard for an agent acting on this principal's behalf.

        The returned permissions are the agent's own grants intersected with
        its owner's, so an agent can never be used to reach data the person
        responsible for it cannot reach.
        """
        capped = load_agent_permission_set(
            self._db, agent_id, self.principal, self.workspace_id
        )
        return Guard(capped, self._db, capped.principal, self.workspace_id)

    # -- internals ------------------------------------------------------

    def _error(
        self,
        privilege: Privilege,
        securable: Securable,
        reason: str,
        detail: str | None,
    ) -> HTTPException:
        if reason == Decision.NO_WORKSPACE_ACCESS:
            return HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace.",
            )

        # Existence is itself information. Only admit that the object exists to
        # a principal already allowed to see that it does.
        #
        # A broken USE chain lands here too, and deliberately: if you cannot
        # traverse the catalog, you are not entitled to learn what is inside
        # it. The route to access is the catalog browser, which shows what the
        # principal *can* BROWSE, not an error message naming what they cannot.
        if privilege is Privilege.BROWSE or not self.can(Privilege.BROWSE, securable):
            return HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{securable.type.value} not found",
            )

        if reason == Decision.AGENT_CEILING:
            return HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This agent may not access {securable.full_name}: its owner "
                    f"does not have that access."
                ),
            )
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{privilege.value} on {securable.full_name} is required.",
        )

    def _audit(
        self,
        privilege: Privilege,
        securable: Securable,
        allowed: bool,
        reason: str,
    ) -> None:
        if allowed and privilege not in _AUDITED_ON_ALLOW:
            return
        try:
            from app.governance.service import record_access_decision

            record_access_decision(
                self._db,
                workspace_id=self.workspace_id,
                principal=self.principal,
                securable=securable,
                privilege=privilege,
                allowed=allowed,
                reason=reason,
            )
        except Exception:  # pragma: no cover
            # An audit failure must not convert an allowed request into an
            # error, nor a denial into an allow. Log and carry on; the
            # decision itself is unaffected.
            logger.exception(
                "Failed to audit %s %s on %s",
                "allow" if allowed else "deny",
                privilege.value,
                securable.full_name,
            )


def get_guard(
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_system_db),
) -> Guard:
    """Load the caller's permissions once per request."""
    cached = getattr(request.state, "governance_guard", None)
    if cached is not None:
        return cached

    workspace_id = current_workspace_id(request)
    guard = Guard(
        load_permission_set(db, principal, workspace_id),
        db,
        principal,
        workspace_id,
    )
    request.state.governance_guard = guard
    return guard


# ----------------------------------------------------------------------
# Route-level dependency
# ----------------------------------------------------------------------


def require(
    privilege: Privilege,
    securable_from: Callable[[dict[str, str]], Securable],
) -> Callable[..., None]:
    """Build a route dependency enforcing ``privilege``.

    ``securable_from`` receives the request's path parameters. Use this when
    the securable is fully determined by the URL; use ``Guard`` inside the
    handler when it is not.
    """

    def _dependency(request: Request, guard: Guard = Depends(get_guard)) -> None:
        securable = securable_from(request.path_params)  # type: ignore[arg-type]
        guard.require(privilege, securable)

    return _dependency


def require_any(
    privileges: Sequence[Privilege],
    securable_from: Callable[[dict[str, str]], Securable],
) -> Callable[..., None]:
    """As ``require``, but any one of ``privileges`` suffices.

    For endpoints that serve more than one intent — a notebook detail view is
    reachable by someone who may run it or someone who may edit it.
    """

    def _dependency(request: Request, guard: Guard = Depends(get_guard)) -> None:
        securable = securable_from(request.path_params)  # type: ignore[arg-type]
        if any(guard.can(p, securable) for p in privileges):
            return
        guard.require(privileges[0], securable)

    return _dependency
