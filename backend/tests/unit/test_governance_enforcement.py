"""Tests for the enforcement layer.

The decision itself is covered by test_governance_resolver. What matters here
is what a caller *observes*: which status code, what the message reveals, and
that list endpoints filter rather than refuse.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.governance.dependencies import Guard
from app.governance.models import AccessAuditLog
from app.governance.privileges import Privilege
from app.governance.resolver import PermissionSet, Principal, _Grant
from app.governance.securable import Securable

WORKSPACE = "11111111-1111-1111-1111-111111111111"
USER_ID = "33333333-3333-3333-3333-333333333333"

MAIN = Securable.catalog_("main")
SALES = Securable.schema_("main", "sales")
ORDERS = Securable.table("main", "sales", "orders")
REFUNDS = Securable.table("main", "sales", "refunds")
SALARIES = Securable.table("main", "hr", "salaries")

USE_CHAIN = [
    _Grant(MAIN, frozenset({Privilege.USE})),
    _Grant(SALES, frozenset({Privilege.USE})),
]


def make_guard(db_session, grants=(), workspace_role="analyst") -> Guard:
    principal = Principal(
        id=USER_ID,
        workspace_roles={WORKSPACE: workspace_role} if workspace_role else {},
    )
    permissions = PermissionSet(principal, WORKSPACE, list(grants), frozenset())
    return Guard(permissions, db_session, principal, WORKSPACE)


class TestStatusCodes:
    def test_invisible_object_is_404_not_403(self, db_session):
        """403 on an object you cannot see confirms it exists.

        That turns an unauthorized caller into an enumeration oracle for table
        names, which are themselves sensitive.
        """
        guard = make_guard(db_session, USE_CHAIN)
        with pytest.raises(HTTPException) as exc:
            guard.require(Privilege.SELECT, ORDERS)
        assert exc.value.status_code == 404
        assert "orders" not in str(exc.value.detail)

    def test_visible_but_insufficient_is_403(self, db_session):
        """Actionable: the user knows the object and what to request."""
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.BROWSE}))]
        guard = make_guard(db_session, grants)
        with pytest.raises(HTTPException) as exc:
            guard.require(Privilege.SELECT, ORDERS)
        assert exc.value.status_code == 403
        assert "SELECT" in exc.value.detail

    def test_broken_use_chain_is_404_even_with_an_asset_grant(self, db_session):
        """A grant you cannot traverse to must not reveal that the object exists.

        Otherwise the catalog boundary leaks names to anyone holding a stale
        asset-level grant.
        """
        grants = [_Grant(ORDERS, frozenset({Privilege.BROWSE, Privilege.SELECT}))]
        guard = make_guard(db_session, grants)
        with pytest.raises(HTTPException) as exc:
            guard.require(Privilege.SELECT, ORDERS)
        assert exc.value.status_code == 404

    def test_no_workspace_membership_is_403(self, db_session):
        guard = make_guard(db_session, USE_CHAIN, workspace_role=None)
        with pytest.raises(HTTPException) as exc:
            guard.require(Privilege.SELECT, ORDERS)
        assert exc.value.status_code == 403
        assert "workspace" in exc.value.detail.lower()

    def test_allowed_request_does_not_raise(self, db_session):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        make_guard(db_session, grants).require(Privilege.SELECT, ORDERS)


class TestFiltering:
    def test_list_filters_rather_than_refuses(self, db_session):
        grants = [
            _Grant(MAIN, frozenset({Privilege.USE})),
            _Grant(SALES, frozenset({Privilege.USE, Privilege.SELECT})),
        ]
        guard = make_guard(db_session, grants)
        visible = guard.filter(Privilege.SELECT, [ORDERS, REFUNDS, SALARIES])
        assert [s.full_name for s in visible] == ["main.sales.orders", "main.sales.refunds"]

    def test_filter_accepts_a_projection_for_domain_objects(self, db_session):
        """Handlers hold ORM rows, not Securables."""
        grants = [
            _Grant(MAIN, frozenset({Privilege.USE})),
            _Grant(SALES, frozenset({Privilege.USE, Privilege.SELECT})),
        ]
        rows = [
            {"catalog": "main", "schema": "sales", "name": "orders"},
            {"catalog": "main", "schema": "hr", "name": "salaries"},
        ]
        visible = make_guard(db_session, grants).filter(
            Privilege.SELECT,
            rows,
            lambda r: Securable.table(r["catalog"], r["schema"], r["name"]),
        )
        assert [r["name"] for r in visible] == ["orders"]

    def test_visible_prefixes_supports_pushing_the_filter_into_sql(self, db_session):
        grants = [
            _Grant(MAIN, frozenset({Privilege.USE})),
            _Grant(SALES, frozenset({Privilege.SELECT})),
        ]
        assert make_guard(db_session, grants).visible_prefixes(Privilege.SELECT) == [
            ("main", "sales")
        ]


class TestAudit:
    def _events(self, db_session):
        db_session.flush()
        return db_session.execute(
            select(AccessAuditLog).where(AccessAuditLog.event_type == "access")
        ).scalars().all()

    def test_denials_are_always_audited(self, db_session):
        guard = make_guard(db_session, USE_CHAIN)
        with pytest.raises(HTTPException):
            guard.require(Privilege.SELECT, ORDERS)
        events = self._events(db_session)
        assert len(events) == 1
        assert events[0].decision == "deny"

    def test_allowed_reads_are_not_audited(self, db_session):
        """Auditing every read would bury the events a review looks for."""
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        make_guard(db_session, grants).require(Privilege.SELECT, ORDERS)
        assert self._events(db_session) == []

    def test_allowed_writes_are_audited(self, db_session):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.MODIFY}))]
        make_guard(db_session, grants).require(Privilege.MODIFY, ORDERS)
        events = self._events(db_session)
        assert len(events) == 1
        assert events[0].decision == "allow"
        assert events[0].privilege == "MODIFY"

    def test_can_does_not_audit(self, db_session):
        """`can` shapes a response; it is not an access attempt."""
        guard = make_guard(db_session, USE_CHAIN)
        assert not guard.can(Privilege.MODIFY, ORDERS)
        assert self._events(db_session) == []
