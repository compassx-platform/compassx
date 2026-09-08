"""Tests for grant administration.

These cover the rules enforced at the write boundary — the ones that decide
whether a grant may be created at all: privilege applicability, the MANAGE
requirement, the agent ceiling, idempotency, and audit.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.governance import service
from app.governance.models import (
    AccessAuditLog,
    AgentPrincipal,
    ObjectGrant,
    SecurableOwner,
)
from app.governance.privileges import Privilege
from app.governance.resolver import Principal, load_permission_set
from app.governance.securable import Securable
from app.governance.service import GovernanceError, PermissionDenied

WORKSPACE = "11111111-1111-1111-1111-111111111111"
ADMIN_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "33333333-3333-3333-3333-333333333333"
OTHER_ID = "44444444-4444-4444-4444-444444444444"
AGENT_PRINCIPAL_ID = "55555555-5555-5555-5555-555555555555"

ORDERS = Securable.table("main", "sales", "orders")
SALES = Securable.schema_("main", "sales")
MAIN = Securable.catalog_("main")
NIGHTLY = Securable.job("job-nightly")


@pytest.fixture()
def admin() -> Principal:
    """Account admin — holds MANAGE everywhere, so grants always pass."""
    return Principal(id=ADMIN_ID, is_account_admin=True)


@pytest.fixture()
def analyst() -> Principal:
    return Principal(id=USER_ID, workspace_roles={WORKSPACE: "analyst"})


def _grant(db, admin, securable, principal_id, privileges, principal_type="user"):
    return service.grant(
        db,
        workspace_id=WORKSPACE,
        securable=securable,
        principal_id=principal_id,
        principal_type=principal_type,
        privileges=privileges,
        actor=admin,
    )


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


class TestOwnership:
    def test_set_owner_creates_a_single_row(self, db_session, admin):
        service.set_owner(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            owner_principal_id=USER_ID,
            actor=admin,
        )
        owner = service.get_owner(db_session, WORKSPACE, ORDERS)
        assert owner is not None
        assert owner.owner_principal_id == USER_ID

    def test_set_owner_twice_replaces_rather_than_duplicates(self, db_session, admin):
        for principal in (USER_ID, OTHER_ID):
            service.set_owner(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                owner_principal_id=principal,
                actor=admin,
            )
        rows = db_session.execute(
            select(SecurableOwner).where(SecurableOwner.workspace_id == WORKSPACE)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].owner_principal_id == OTHER_ID

    def test_owner_of_a_container_is_addressed_without_an_asset(self, db_session, admin):
        """schema_name/asset_name are NULL for a catalog; lookup must use IS NULL."""
        service.set_owner(
            db_session,
            workspace_id=WORKSPACE,
            securable=MAIN,
            owner_principal_id=USER_ID,
            actor=admin,
        )
        assert service.get_owner(db_session, WORKSPACE, MAIN) is not None
        assert service.get_owner(db_session, WORKSPACE, ORDERS) is None

    def test_transfer_requires_manage(self, db_session, analyst):
        service.set_owner(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            owner_principal_id=OTHER_ID,
        )
        with pytest.raises(PermissionDenied):
            service.transfer_ownership(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                new_owner_principal_id=USER_ID,
                new_owner_principal_type="user",
                actor=analyst,
            )

    def test_owner_may_transfer_their_own_object(self, db_session, analyst):
        """Ownership implies MANAGE, so an owner can hand the object on."""
        service.set_owner(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            owner_principal_id=USER_ID,
        )
        service.transfer_ownership(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            new_owner_principal_id=OTHER_ID,
            new_owner_principal_type="user",
            actor=analyst,
        )
        owner = service.get_owner(db_session, WORKSPACE, ORDERS)
        assert owner.owner_principal_id == OTHER_ID


# ---------------------------------------------------------------------------
# Grant
# ---------------------------------------------------------------------------


class TestGrant:
    def test_grant_makes_the_resolver_allow(self, db_session, admin, analyst):
        _grant(db_session, admin, MAIN, USER_ID, ["USE"])
        _grant(db_session, admin, SALES, USER_ID, ["USE"])
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])

        permissions = load_permission_set(db_session, analyst, WORKSPACE)
        assert permissions.can(Privilege.SELECT, ORDERS)

    def test_bundle_is_stored_as_individual_privileges(self, db_session, admin):
        created = _grant(db_session, admin, SALES, USER_ID, ["viewer"])
        assert {row.privilege for row in created} == {"BROWSE", "SELECT", "USE"}

    def test_bundle_drops_members_that_do_not_apply(self, db_session, admin):
        """USE is meaningless on a table; the rest of the bundle still applies."""
        created = _grant(db_session, admin, ORDERS, USER_ID, ["viewer"])
        assert {row.privilege for row in created} == {"BROWSE", "SELECT"}

    def test_explicitly_naming_an_inapplicable_privilege_is_an_error(
        self, db_session, admin
    ):
        """Silently dropping this would look like access was conferred."""
        with pytest.raises(ValueError):
            _grant(db_session, admin, NIGHTLY, USER_ID, ["SELECT"])

    def test_unknown_privilege_name_is_rejected(self, db_session, admin):
        with pytest.raises(ValueError):
            _grant(db_session, admin, ORDERS, USER_ID, ["NOT_A_PRIVILEGE"])

    def test_grant_is_idempotent(self, db_session, admin):
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        second = _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        assert second == []

        rows = db_session.execute(
            select(ObjectGrant).where(ObjectGrant.principal_id == USER_ID)
        ).scalars().all()
        assert len(rows) == 1

    def test_granting_requires_manage_on_the_securable(self, db_session, analyst):
        with pytest.raises(PermissionDenied):
            service.grant(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                principal_id=OTHER_ID,
                principal_type="user",
                privileges=["SELECT"],
                actor=analyst,
            )

    def test_a_grant_does_not_confer_the_right_to_re_grant(self, db_session, admin, analyst):
        """SELECT lets you read; it does not let you hand SELECT to others."""
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        with pytest.raises(PermissionDenied):
            service.grant(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                principal_id=OTHER_ID,
                principal_type="user",
                privileges=["SELECT"],
                actor=analyst,
            )

    def test_manage_holder_may_re_grant(self, db_session, admin, analyst):
        _grant(db_session, admin, MAIN, USER_ID, ["USE"])
        _grant(db_session, admin, SALES, USER_ID, ["USE"])
        _grant(db_session, admin, ORDERS, USER_ID, ["MANAGE"])
        service.grant(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            principal_id=OTHER_ID,
            principal_type="user",
            privileges=["SELECT"],
            actor=analyst,
        )
        assert service.list_grants(db_session, WORKSPACE, ORDERS)

    def test_manage_without_the_use_chain_does_not_confer_re_grant(
        self, db_session, admin, analyst
    ):
        """MANAGE is gated by the USE chain like every other privilege.

        Administering an object you cannot traverse to is not administration.
        """
        _grant(db_session, admin, ORDERS, USER_ID, ["MANAGE"])
        with pytest.raises(PermissionDenied):
            service.grant(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                principal_id=OTHER_ID,
                principal_type="user",
                privileges=["SELECT"],
                actor=analyst,
            )


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


class TestRevoke:
    def test_revoke_removes_access(self, db_session, admin, analyst):
        _grant(db_session, admin, MAIN, USER_ID, ["USE"])
        _grant(db_session, admin, SALES, USER_ID, ["USE"])
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])

        removed = service.revoke(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            principal_id=USER_ID,
            privileges=["SELECT"],
            actor=admin,
        )
        assert removed == 1
        assert not load_permission_set(db_session, analyst, WORKSPACE).can(
            Privilege.SELECT, ORDERS
        )

    def test_revoke_does_not_touch_a_sibling_securable(self, db_session, admin):
        refunds = Securable.table("main", "sales", "refunds")
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        _grant(db_session, admin, refunds, USER_ID, ["SELECT"])

        service.revoke(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            principal_id=USER_ID,
            privileges=["SELECT"],
            actor=admin,
        )
        assert service.list_grants(db_session, WORKSPACE, refunds)

    def test_revoking_a_container_grant_matches_on_null_path_segments(
        self, db_session, admin
    ):
        """A catalog grant has NULL schema/asset; equality would never match."""
        _grant(db_session, admin, MAIN, USER_ID, ["USE"])
        removed = service.revoke(
            db_session,
            workspace_id=WORKSPACE,
            securable=MAIN,
            principal_id=USER_ID,
            privileges=["USE"],
            actor=admin,
        )
        assert removed == 1

    def test_revoking_what_was_never_granted_is_not_an_error(self, db_session, admin):
        assert (
            service.revoke(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                principal_id=USER_ID,
                privileges=["SELECT"],
                actor=admin,
            )
            == 0
        )

    def test_revoke_requires_manage(self, db_session, analyst):
        with pytest.raises(PermissionDenied):
            service.revoke(
                db_session,
                workspace_id=WORKSPACE,
                securable=ORDERS,
                principal_id=OTHER_ID,
                privileges=["SELECT"],
                actor=analyst,
            )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class TestListing:
    def test_list_grants_is_scoped_to_one_securable(self, db_session, admin):
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        _grant(db_session, admin, SALES, USER_ID, ["USE"])

        names = {g.privilege for g in service.list_grants(db_session, WORKSPACE, ORDERS)}
        assert names == {"SELECT"}

    def test_list_principal_grants_spans_securables(self, db_session, admin):
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        _grant(db_session, admin, SALES, USER_ID, ["USE"])
        _grant(db_session, admin, ORDERS, OTHER_ID, ["SELECT"])

        held = service.list_principal_grants(db_session, WORKSPACE, USER_ID)
        assert len(held) == 2


# ---------------------------------------------------------------------------
# Agent ceiling
# ---------------------------------------------------------------------------


class TestAgentCeiling:
    def _provision(self, db_session, owner_principal_id=USER_ID):
        row = AgentPrincipal(
            agent_id="nova-1",
            principal_id=AGENT_PRINCIPAL_ID,
            workspace_id=WORKSPACE,
            owner_principal_id=owner_principal_id,
            owner_principal_type="user",
        )
        db_session.add(row)
        db_session.flush()
        return row

    def test_ensure_agent_principal_is_idempotent(self, db_session):
        first = service.ensure_agent_principal(
            db_session,
            agent_id="nova-1",
            workspace_id=WORKSPACE,
            owner_principal_id=USER_ID,
        )
        second = service.ensure_agent_principal(
            db_session,
            agent_id="nova-1",
            workspace_id=WORKSPACE,
            owner_principal_id=OTHER_ID,
        )
        assert first.id == second.id
        assert second.owner_principal_id == USER_ID

    def test_agent_cannot_be_granted_more_than_its_owner_holds(self, db_session, admin):
        self._provision(db_session)
        with pytest.raises(GovernanceError, match="owner does not hold"):
            _grant(
                db_session,
                admin,
                ORDERS,
                AGENT_PRINCIPAL_ID,
                ["SELECT"],
                principal_type="service",
            )

    def test_agent_grant_succeeds_within_the_ceiling(self, db_session, admin):
        self._provision(db_session)
        _grant(db_session, admin, MAIN, USER_ID, ["USE"])
        _grant(db_session, admin, SALES, USER_ID, ["USE"])
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])

        created = _grant(
            db_session,
            admin,
            ORDERS,
            AGENT_PRINCIPAL_ID,
            ["SELECT"],
            principal_type="service",
        )
        assert [row.privilege for row in created] == ["SELECT"]

    def test_ceiling_is_not_applied_to_ordinary_users(self, db_session, admin):
        """principal_type 'user' must not be routed through the agent check."""
        created = _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        assert len(created) == 1


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAudit:
    def _events(self, db_session, event_type):
        return db_session.execute(
            select(AccessAuditLog).where(AccessAuditLog.event_type == event_type)
        ).scalars().all()

    def test_every_granted_privilege_is_audited(self, db_session, admin):
        _grant(db_session, admin, SALES, USER_ID, ["viewer"])
        events = self._events(db_session, "grant")
        assert {e.privilege for e in events} == {"BROWSE", "SELECT", "USE"}
        assert all(e.securable_name == "main.sales" for e in events)

    def test_revoke_is_audited(self, db_session, admin):
        _grant(db_session, admin, ORDERS, USER_ID, ["SELECT"])
        service.revoke(
            db_session,
            workspace_id=WORKSPACE,
            securable=ORDERS,
            principal_id=USER_ID,
            privileges=["SELECT"],
            actor=admin,
        )
        assert len(self._events(db_session, "revoke")) == 1

    def test_denials_are_recorded_not_only_allows(self, db_session, analyst):
        service.record_access_decision(
            db_session,
            workspace_id=WORKSPACE,
            principal=analyst,
            securable=ORDERS,
            privilege=Privilege.SELECT,
            allowed=False,
            reason="no_grant",
        )
        db_session.flush()
        event = self._events(db_session, "access")[0]
        assert event.decision == "deny"
        assert event.reason == "no_grant"

    def test_agent_access_records_the_invoking_user(self, db_session):
        """Attribution must survive an agent acting on someone's behalf."""
        agent = Principal(
            id=AGENT_PRINCIPAL_ID,
            type="service",
            workspace_roles={WORKSPACE: "analyst"},
            on_behalf_of=USER_ID,
        )
        service.record_access_decision(
            db_session,
            workspace_id=WORKSPACE,
            principal=agent,
            securable=ORDERS,
            privilege=Privilege.SELECT,
            allowed=True,
            reason="direct_grant",
        )
        db_session.flush()
        event = self._events(db_session, "access")[0]
        assert event.principal_id == AGENT_PRINCIPAL_ID
        assert event.on_behalf_of_principal_id == USER_ID
