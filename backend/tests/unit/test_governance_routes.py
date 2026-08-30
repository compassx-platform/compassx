"""Tests for the governance API.

Covers the contract a UI depends on: status codes, idempotency, and that the
read endpoints do not become a way to discover access you are not entitled to
know about.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_system_db
from app.governance import routes
from app.governance.dependencies import Guard, get_guard
from app.governance.resolver import PermissionSet, Principal, load_permission_set

WORKSPACE = "11111111-1111-1111-1111-111111111111"
ADMIN_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "33333333-3333-3333-3333-333333333333"
OTHER_ID = "44444444-4444-4444-4444-444444444444"


def _client(db_session, principal: Principal) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)

    def _override_guard() -> Guard:
        permissions = load_permission_set(db_session, principal, WORKSPACE)
        return Guard(permissions, db_session, principal, WORKSPACE)

    app.dependency_overrides[get_guard] = _override_guard
    app.dependency_overrides[get_system_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def admin_client(db_session) -> TestClient:
    return _client(db_session, Principal(id=ADMIN_ID, is_account_admin=True))


@pytest.fixture()
def analyst_client(db_session) -> TestClient:
    return _client(
        db_session,
        Principal(id=USER_ID, workspace_roles={WORKSPACE: "analyst"}),
    )


def _grant_body(**overrides) -> dict:
    body = {
        "securable_type": "table",
        "name": "main.sales.orders",
        "principal_id": USER_ID,
        "principal_type": "user",
        "privileges": ["SELECT"],
    }
    body.update(overrides)
    return body


class TestVocabulary:
    def test_privileges_endpoint_describes_the_grant_dialog(self, admin_client):
        """Served by the backend so the UI cannot offer privileges we ignore."""
        body = admin_client.get("/api/v1/governance/privileges").json()
        assert "SELECT" in body["privileges"]
        assert body["bundles"]["viewer"] == ["BROWSE", "SELECT", "USE"]
        assert "USE" not in body["applicable"]["table"]


class TestGrantEndpoint:
    def test_grant_returns_201_and_the_created_rows(self, admin_client):
        response = admin_client.post("/api/v1/governance/grants", json=_grant_body())
        assert response.status_code == 201
        assert [row["privilege"] for row in response.json()] == ["SELECT"]
        assert response.json()[0]["securable_name"] == "main.sales.orders"

    def test_re_granting_is_idempotent(self, admin_client):
        admin_client.post("/api/v1/governance/grants", json=_grant_body())
        second = admin_client.post("/api/v1/governance/grants", json=_grant_body())
        assert second.status_code == 201
        assert second.json() == []

    def test_bundle_expands_to_individual_privileges(self, admin_client):
        response = admin_client.post(
            "/api/v1/governance/grants",
            json=_grant_body(securable_type="schema", name="main.sales", privileges=["viewer"]),
        )
        assert sorted(r["privilege"] for r in response.json()) == ["BROWSE", "SELECT", "USE"]

    def test_inapplicable_privilege_is_400(self, admin_client):
        response = admin_client.post(
            "/api/v1/governance/grants",
            json=_grant_body(securable_type="job", name="job-nightly"),
        )
        assert response.status_code == 400
        assert "not applicable" in response.json()["detail"]

    def test_unknown_privilege_is_400(self, admin_client):
        response = admin_client.post(
            "/api/v1/governance/grants", json=_grant_body(privileges=["SUPERUSER"])
        )
        assert response.status_code == 400

    def test_malformed_path_is_400_not_500(self, admin_client):
        """A table needs three segments; two would match a whole schema."""
        response = admin_client.post(
            "/api/v1/governance/grants", json=_grant_body(name="main.sales")
        )
        assert response.status_code == 400

    def test_unknown_securable_type_is_422(self, admin_client):
        response = admin_client.post(
            "/api/v1/governance/grants", json=_grant_body(securable_type="warehouse")
        )
        assert response.status_code == 422

    def test_granting_without_manage_is_403(self, analyst_client):
        response = analyst_client.post("/api/v1/governance/grants", json=_grant_body())
        assert response.status_code == 403


class TestRevokeEndpoint:
    def test_revoke_reports_what_it_removed(self, admin_client):
        admin_client.post("/api/v1/governance/grants", json=_grant_body())
        response = admin_client.post(
            "/api/v1/governance/grants/revoke",
            json={
                "securable_type": "table",
                "name": "main.sales.orders",
                "principal_id": USER_ID,
                "privileges": ["SELECT"],
            },
        )
        assert response.status_code == 200
        assert response.json() == {"revoked": 1}

    def test_revoking_without_manage_is_403(self, analyst_client):
        response = analyst_client.post(
            "/api/v1/governance/grants/revoke",
            json={
                "securable_type": "table",
                "name": "main.sales.orders",
                "principal_id": OTHER_ID,
                "privileges": ["SELECT"],
            },
        )
        assert response.status_code == 403


class TestListGrants:
    def test_listing_grants_requires_manage(self, admin_client, analyst_client):
        """Who holds access to an object is itself sensitive."""
        admin_client.post("/api/v1/governance/grants", json=_grant_body())
        response = analyst_client.get(
            "/api/v1/governance/grants",
            params={"securable_type": "table", "name": "main.sales.orders"},
        )
        assert response.status_code in (403, 404)

    def test_admin_sees_the_permissions_tab(self, admin_client):
        admin_client.post("/api/v1/governance/grants", json=_grant_body())
        response = admin_client.get(
            "/api/v1/governance/grants",
            params={"securable_type": "table", "name": "main.sales.orders"},
        )
        assert response.status_code == 200
        assert [row["privilege"] for row in response.json()] == ["SELECT"]

    def test_a_principal_may_review_their_own_access(self, analyst_client):
        response = analyst_client.get(f"/api/v1/governance/principals/{USER_ID}/grants")
        assert response.status_code == 200

    def test_reviewing_another_principal_requires_workspace_admin(self, analyst_client):
        response = analyst_client.get(f"/api/v1/governance/principals/{OTHER_ID}/grants")
        assert response.status_code == 403


class TestOwnership:
    def test_owner_is_null_before_assignment(self, admin_client):
        response = admin_client.get(
            "/api/v1/governance/owner",
            params={"securable_type": "table", "name": "main.sales.orders"},
        )
        assert response.status_code == 200
        assert response.json() is None

    def test_transfer_then_read_back(self, admin_client):
        admin_client.put(
            "/api/v1/governance/owner",
            json={
                "securable_type": "table",
                "name": "main.sales.orders",
                "owner_principal_id": USER_ID,
                "owner_principal_type": "user",
            },
        )
        body = admin_client.get(
            "/api/v1/governance/owner",
            params={"securable_type": "table", "name": "main.sales.orders"},
        ).json()
        assert body["owner_principal_id"] == USER_ID

    def test_transfer_without_manage_is_403(self, analyst_client):
        response = analyst_client.put(
            "/api/v1/governance/owner",
            json={
                "securable_type": "table",
                "name": "main.sales.orders",
                "owner_principal_id": OTHER_ID,
                "owner_principal_type": "user",
            },
        )
        assert response.status_code == 403


class TestEffectivePermissions:
    def test_explains_a_denial(self, analyst_client):
        body = analyst_client.get(
            "/api/v1/governance/effective",
            params={"securable_type": "table", "name": "main.sales.orders"},
        ).json()
        assert body["privileges"] == []
        assert body["decisions"]["SELECT"].startswith("use_chain_broken")

    def test_explains_an_allow(self, admin_client, analyst_client):
        for securable_type, name, privileges in [
            ("catalog", "main", ["USE"]),
            ("schema", "main.sales", ["USE"]),
            ("table", "main.sales.orders", ["SELECT"]),
        ]:
            admin_client.post(
                "/api/v1/governance/grants",
                json=_grant_body(
                    securable_type=securable_type, name=name, privileges=privileges
                ),
            )
        body = analyst_client.get(
            "/api/v1/governance/effective",
            params={"securable_type": "table", "name": "main.sales.orders"},
        ).json()
        assert "SELECT" in body["privileges"]
        assert body["decisions"]["SELECT"].startswith("direct_grant")

    def test_only_applicable_privileges_are_reported(self, analyst_client):
        body = analyst_client.get(
            "/api/v1/governance/effective",
            params={"securable_type": "job", "name": "job-nightly"},
        ).json()
        assert set(body["decisions"]) == {"BROWSE", "EDIT", "EXECUTE", "MANAGE"}

    def test_inspecting_another_principal_requires_workspace_admin(self, analyst_client):
        response = analyst_client.get(
            "/api/v1/governance/effective",
            params={
                "securable_type": "table",
                "name": "main.sales.orders",
                "principal_id": OTHER_ID,
            },
        )
        assert response.status_code == 403
