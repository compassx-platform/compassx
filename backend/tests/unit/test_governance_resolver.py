"""Tests for the governance permission resolver.

These cover the rules that are easy to get subtly wrong and expensive to get
wrong in production: the USE chain, inheritance boundaries, sibling isolation,
and the agent ownership ceiling.
"""
from __future__ import annotations

import pytest

from app.governance.privileges import (
    Privilege,
    SecurableType,
    expand_bundle,
    validate_privilege_for_securable,
)
from app.governance.resolver import (
    Decision,
    PermissionSet,
    Principal,
    _CappedPermissionSet,
    _Grant,
)
from app.governance.securable import Securable

WORKSPACE = "ws-1"
ORDERS = Securable.table("main", "sales", "orders")
MAIN = Securable.catalog_("main")
SALES = Securable.schema_("main", "sales")

USE_CHAIN = [
    _Grant(MAIN, frozenset({Privilege.USE})),
    _Grant(SALES, frozenset({Privilege.USE})),
]


def make_set(
    grants=(),
    owned=frozenset(),
    workspace_role: str | None = "analyst",
    is_account_admin: bool = False,
    principal_id: str = "user-1",
) -> PermissionSet:
    principal = Principal(
        id=principal_id,
        is_account_admin=is_account_admin,
        group_ids=("group-1",),
        workspace_roles={WORKSPACE: workspace_role} if workspace_role else {},
    )
    return PermissionSet(principal, WORKSPACE, list(grants), owned)


# ---------------------------------------------------------------------------
# Securable addressing
# ---------------------------------------------------------------------------


class TestSecurable:
    def test_ancestors_are_outermost_first(self):
        assert [a.full_name for a in ORDERS.ancestors()] == ["main", "main.sales"]

    def test_catalog_and_schema_grants_cover_descendant(self):
        assert MAIN.covers(ORDERS)
        assert SALES.covers(ORDERS)

    def test_sibling_containers_do_not_cover(self):
        assert not Securable.schema_("main", "hr").covers(ORDERS)
        assert not Securable.catalog_("dev").covers(ORDERS)

    def test_same_name_different_type_is_distinct(self):
        """A notebook and a table may share a name within a schema."""
        notebook = Securable.notebook("main", "sales", "orders")
        assert not ORDERS.covers(notebook)
        assert not notebook.covers(ORDERS)

    def test_workspace_securables_never_cover_siblings(self):
        job_a, job_b = Securable.job("job-a"), Securable.job("job-b")
        assert job_a.covers(job_a)
        assert not job_a.covers(job_b)

    def test_workspace_securables_have_no_use_chain(self):
        assert Securable.job("job-a").ancestors() == []

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"type": SecurableType.TABLE, "catalog": "main"},          # missing schema
            {"type": SecurableType.TABLE, "catalog": "main", "schema": "sales"},  # missing asset
            {"type": SecurableType.CATALOG, "catalog": "main", "schema": "sales"},  # over-specified
        ],
    )
    def test_malformed_securables_are_rejected(self, kwargs):
        with pytest.raises(ValueError):
            Securable(**kwargs)


# ---------------------------------------------------------------------------
# Privilege vocabulary
# ---------------------------------------------------------------------------


class TestPrivileges:
    def test_bundle_expands(self):
        assert expand_bundle("viewer") == frozenset(
            {Privilege.BROWSE, Privilege.SELECT, Privilege.USE}
        )

    def test_raw_privilege_expands_to_itself(self):
        assert expand_bundle("SELECT") == frozenset({Privilege.SELECT})

    def test_unknown_name_raises_rather_than_granting_nothing(self):
        with pytest.raises(ValueError):
            expand_bundle("NOT_A_PRIVILEGE")

    def test_inapplicable_privilege_is_rejected_at_grant_time(self):
        with pytest.raises(ValueError):
            validate_privilege_for_securable(Privilege.SELECT, SecurableType.JOB)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class TestResolution:
    def test_denies_by_default(self):
        assert not make_set().can(Privilege.SELECT, ORDERS)

    def test_select_without_use_chain_is_denied(self):
        """The USE chain is the gate that makes catalog boundaries real."""
        result = make_set([_Grant(ORDERS, frozenset({Privilege.SELECT}))]).check(
            Privilege.SELECT, ORDERS
        )
        assert not result.allowed
        assert result.reason == Decision.USE_CHAIN_BROKEN
        assert result.detail == "main"

    def test_direct_grant_with_full_chain_allows(self):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        result = make_set(grants).check(Privilege.SELECT, ORDERS)
        assert result.allowed
        assert result.reason == Decision.DIRECT_GRANT

    def test_catalog_grant_is_inherited(self):
        grants = [_Grant(MAIN, frozenset({Privilege.USE, Privilege.SELECT}))]
        result = make_set(grants).check(Privilege.SELECT, ORDERS)
        assert result.allowed
        assert result.reason == Decision.INHERITED_GRANT

    def test_unrelated_privilege_is_not_granted(self):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        assert not make_set(grants).can(Privilege.MODIFY, ORDERS)

    def test_manage_implies_applicable_privileges(self):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.MANAGE}))]
        assert make_set(grants).can(Privilege.MODIFY, ORDERS)

    def test_no_workspace_membership_denies(self):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        result = make_set(grants, workspace_role=None).check(Privilege.SELECT, ORDERS)
        assert not result.allowed
        assert result.reason == Decision.NO_WORKSPACE_ACCESS

    def test_workspace_admin_allowed_within_workspace(self):
        result = make_set(workspace_role="workspace_admin").check(Privilege.SELECT, ORDERS)
        assert result.allowed
        assert result.reason == Decision.WORKSPACE_ADMIN

    def test_account_admin_break_glass(self):
        result = make_set(workspace_role=None, is_account_admin=True).check(
            Privilege.SELECT, ORDERS
        )
        assert result.allowed
        assert result.reason == Decision.ACCOUNT_ADMIN

    def test_owner_holds_applicable_privileges(self):
        owned = frozenset({("table", "main", "sales", "orders")})
        result = make_set(USE_CHAIN, owned=owned).check(Privilege.MODIFY, ORDERS)
        assert result.allowed
        assert result.reason == Decision.OWNER

    def test_grants_apply_through_group_membership(self):
        """group-1 is in the principal's group set; its grants must apply."""
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        assert make_set(grants).can(Privilege.SELECT, ORDERS)


class TestListFiltering:
    def test_filter_returns_only_accessible(self):
        grants = [_Grant(SALES, frozenset({Privilege.USE, Privilege.SELECT})),
                  _Grant(MAIN, frozenset({Privilege.USE}))]
        objects = [
            Securable.table("main", "sales", "orders"),
            Securable.table("main", "sales", "refunds"),
            Securable.table("main", "hr", "salaries"),
        ]
        visible = make_set(grants).filter_visible(Privilege.SELECT, objects)
        assert [s.full_name for s in visible] == ["main.sales.orders", "main.sales.refunds"]


class TestAgentCeiling:
    """An agent must never exceed the privileges of its owner."""

    def _sets(self, agent_grants, owner_grants):
        agent = PermissionSet(
            Principal(id="agent-principal", type="service", workspace_roles={WORKSPACE: "analyst"}),
            WORKSPACE,
            list(agent_grants),
            frozenset(),
        )
        owner = PermissionSet(
            Principal(id="owner-1", workspace_roles={WORKSPACE: "analyst"}),
            WORKSPACE,
            list(owner_grants),
            frozenset(),
        )
        return _CappedPermissionSet(agent, owner)

    def test_agent_allowed_when_owner_also_has_access(self):
        grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        assert self._sets(grants, grants).can(Privilege.SELECT, ORDERS)

    def test_agent_denied_when_owner_lacks_access(self):
        agent_grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        result = self._sets(agent_grants, []).check(Privilege.SELECT, ORDERS)
        assert not result.allowed
        assert result.reason == Decision.AGENT_CEILING

    def test_agent_without_own_grant_is_denied_even_if_owner_has_it(self):
        owner_grants = [*USE_CHAIN, _Grant(ORDERS, frozenset({Privilege.SELECT}))]
        assert not self._sets([], owner_grants).can(Privilege.SELECT, ORDERS)
