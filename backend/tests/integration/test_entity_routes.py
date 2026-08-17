"""
Integration tests for entity API routes

Coverage
--------
- POST   /api/v1/entities                          — create entity
- GET    /api/v1/entities                          — list entities
- GET    /api/v1/entities/{name}                   — get entity
- PATCH  /api/v1/entities/{name}                   — update entity
- GET    /api/v1/entities/{name}/fields            — list fields
- POST   /api/v1/entities/{name}/fields            — add field
- PATCH  /api/v1/entities/{name}/fields/{fname}    — update field
- DELETE /api/v1/entities/{name}/fields/{fname}    — delete field
- POST   /api/v1/entities/{name}/records           — create record
- GET    /api/v1/entities/{name}/records           — list records
- GET    /api/v1/entities/{name}/records/{id}      — get record
- PUT    /api/v1/entities/{name}/records/{id}      — update record
- DELETE /api/v1/entities/{name}/records/{id}      — soft-delete record
- GET    /api/v1/entities/{name}/projection        — projection status
- POST   /api/v1/entities/{name}/projection        — enable projection
- HTTP 404 / 422 error responses
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# Entity Definition Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateEntityRoute:

    def test_create_entity_returns_201(self, client: TestClient):
        resp = client.post(
            "/api/v1/entities",
            json={
                "name": "route_entity",
                "entity_type": "generic",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [],
                "system_fields": [],
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201

    def test_create_entity_returns_integer_id(self, client: TestClient):
        resp = client.post(
            "/api/v1/entities",
            json={
                "name": "int_id_entity",
                "entity_type": "generic",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [],
                "system_fields": [],
            },
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_create_entity_with_fields(self, client: TestClient):
        resp = client.post(
            "/api/v1/entities",
            json={
                "name": "entity_with_fields",
                "entity_type": "event",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [
                    {"field_name": "severity", "field_type": "string", "is_required": True, "is_indexed": False},
                    {"field_name": "notes", "field_type": "text", "is_required": False, "is_indexed": False},
                ],
                "system_fields": [],
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        field_names = {f["field_name"] for f in data.get("fields", [])}
        assert "severity" in field_names

    def test_create_entity_duplicate_returns_409(self, client: TestClient):
        payload = {
            "name": "duplicate_route_entity",
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [],
            "system_fields": [],
        }
        client.post("/api/v1/entities", json=payload, headers={"authkey": "test-key"})
        resp = client.post("/api/v1/entities", json=payload, headers={"authkey": "test-key"})
        assert resp.status_code == 409

    def test_create_entity_invalid_name_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/entities",
            json={
                "name": "InvalidName",
                "entity_type": "generic",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [],
                "system_fields": [],
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code in (400, 422)

    def test_create_entity_missing_name_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/entities",
            json={"entity_type": "generic"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422


class TestListEntitiesRoute:

    def test_list_entities_returns_200(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities", headers={"authkey": "test-key"})
        assert resp.status_code == 200

    def test_list_entities_returns_list(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities", headers={"authkey": "test-key"})
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_entities_contains_created_entity(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities", headers={"authkey": "test-key"})
        names = [e["name"] for e in resp.json()]
        assert "test_entity" in names


class TestGetEntityRoute:

    def test_get_entity_returns_200(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities/test_entity", headers={"authkey": "test-key"})
        assert resp.status_code == 200

    def test_get_entity_returns_correct_name(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities/test_entity", headers={"authkey": "test-key"})
        assert resp.json()["name"] == "test_entity"

    def test_get_entity_returns_integer_id(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities/test_entity", headers={"authkey": "test-key"})
        assert isinstance(resp.json()["id"], int)

    def test_get_entity_not_found_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/entities/nonexistent_entity", headers={"authkey": "test-key"})
        assert resp.status_code == 404


class TestUpdateEntityRoute:

    def test_update_entity_returns_200(self, client: TestClient, sample_entity):
        resp = client.patch(
            "/api/v1/entities/test_entity",
            json={"entity_type": "event"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_update_entity_changes_entity_type(self, client: TestClient, sample_entity):
        resp = client.patch(
            "/api/v1/entities/test_entity",
            json={"entity_type": "transaction"},
            headers={"authkey": "test-key"},
        )
        assert resp.json()["entity_type"] == "transaction"

    def test_update_entity_not_found_returns_404(self, client: TestClient):
        resp = client.patch(
            "/api/v1/entities/ghost_entity",
            json={"entity_type": "event"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Entity Field Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityFieldRoutes:

    def test_list_fields_returns_200(self, client: TestClient, sample_entity):
        resp = client.get(
            "/api/v1/entities/test_entity/fields",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_list_fields_returns_list(self, client: TestClient, sample_entity):
        resp = client.get(
            "/api/v1/entities/test_entity/fields",
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_fields_have_integer_ids(self, client: TestClient, sample_entity):
        resp = client.get(
            "/api/v1/entities/test_entity/fields",
            headers={"authkey": "test-key"},
        )
        for field in resp.json():
            assert isinstance(field["id"], int)

    def test_add_field_returns_201(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/entities/test_entity/fields",
            json={"field_name": "new_field", "field_type": "boolean", "is_required": False, "is_indexed": False},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201

    def test_add_field_returns_integer_id(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/entities/test_entity/fields",
            json={"field_name": "another_field", "field_type": "number", "is_required": False, "is_indexed": False},
            headers={"authkey": "test-key"},
        )
        assert isinstance(resp.json()["id"], int)

    def test_add_duplicate_field_returns_409(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/entities/test_entity/fields",
            json={"field_name": "title", "field_type": "string", "is_required": False, "is_indexed": False},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 409

    def test_update_field_returns_200(self, client: TestClient, sample_entity):
        resp = client.patch(
            "/api/v1/entities/test_entity/fields/count",
            json={"is_required": True},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_update_field_not_found_returns_404(self, client: TestClient, sample_entity):
        resp = client.patch(
            "/api/v1/entities/test_entity/fields/ghost_field",
            json={"is_required": True},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_delete_field_returns_204(self, client: TestClient, sample_entity):
        # First add a field to delete
        client.post(
            "/api/v1/entities/test_entity/fields",
            json={"field_name": "temp_field", "field_type": "string", "is_required": False, "is_indexed": False},
            headers={"authkey": "test-key"},
        )
        resp = client.delete(
            "/api/v1/entities/test_entity/fields/temp_field",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 204

    def test_delete_field_not_found_returns_404(self, client: TestClient, sample_entity):
        resp = client.delete(
            "/api/v1/entities/test_entity/fields/nonexistent_field",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Entity Record Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityRecordRoutes:

    def test_create_record_returns_201(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/entities/test_entity/records",
            json={"data": {"title": "Test Record"}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201

    def test_create_record_returns_integer_id(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/entities/test_entity/records",
            json={"data": {"title": "ID Test"}},
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_create_record_missing_required_field_returns_422(
        self, client: TestClient, sample_entity
    ):
        resp = client.post(
            "/api/v1/entities/test_entity/records",
            json={"data": {"count": 5}},  # missing required 'title'
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422

    def test_create_record_unknown_entity_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/entities/ghost_entity/records",
            json={"data": {}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_list_records_returns_200(self, client: TestClient, sample_record):
        resp = client.get(
            "/api/v1/entities/test_entity/records",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_list_records_returns_list(self, client: TestClient, sample_record):
        resp = client.get(
            "/api/v1/entities/test_entity/records",
            headers={"authkey": "test-key"},
        )
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_records_have_integer_ids(self, client: TestClient, sample_record):
        resp = client.get(
            "/api/v1/entities/test_entity/records",
            headers={"authkey": "test-key"},
        )
        for record in resp.json():
            assert isinstance(record["id"], int)

    def test_get_record_returns_200(self, client: TestClient, sample_record):
        resp = client.get(
            f"/api/v1/entities/test_entity/records/{sample_record.id}",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_get_record_returns_correct_id(self, client: TestClient, sample_record):
        resp = client.get(
            f"/api/v1/entities/test_entity/records/{sample_record.id}",
            headers={"authkey": "test-key"},
        )
        assert resp.json()["id"] == sample_record.id

    def test_get_record_not_found_returns_404(self, client: TestClient, sample_entity):
        resp = client.get(
            "/api/v1/entities/test_entity/records/999999",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_update_record_returns_200(self, client: TestClient, sample_record):
        resp = client.put(
            f"/api/v1/entities/test_entity/records/{sample_record.id}",
            json={"data": {"title": "Updated"}, "status": "CLOSED"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_update_record_changes_data(self, client: TestClient, sample_record):
        resp = client.put(
            f"/api/v1/entities/test_entity/records/{sample_record.id}",
            json={"data": {"title": "New Title"}},
            headers={"authkey": "test-key"},
        )
        assert resp.json()["data_json"]["title"] == "New Title"

    def test_update_record_not_found_returns_404(self, client: TestClient, sample_entity):
        resp = client.put(
            "/api/v1/entities/test_entity/records/999999",
            json={"data": {"title": "Ghost"}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_delete_record_returns_204(self, client: TestClient, sample_record):
        resp = client.delete(
            f"/api/v1/entities/test_entity/records/{sample_record.id}",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 204

    def test_delete_record_not_found_returns_404(self, client: TestClient, sample_entity):
        resp = client.delete(
            "/api/v1/entities/test_entity/records/999999",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_deleted_record_not_returned_in_list(self, client: TestClient, sample_record):
        record_id = sample_record.id
        client.delete(
            f"/api/v1/entities/test_entity/records/{record_id}",
            headers={"authkey": "test-key"},
        )
        resp = client.get(
            "/api/v1/entities/test_entity/records",
            headers={"authkey": "test-key"},
        )
        ids = [r["id"] for r in resp.json()]
        assert record_id not in ids


# ═══════════════════════════════════════════════════════════════════════════════
# Projection Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestProjectionRoutes:

    def test_get_projection_status_returns_200(self, client: TestClient, sample_entity):
        resp = client.get(
            "/api/v1/entities/test_entity/projection",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_get_projection_status_not_enabled_by_default(
        self, client: TestClient, sample_entity
    ):
        resp = client.get(
            "/api/v1/entities/test_entity/projection",
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert data["enabled"] is False

    def test_get_projection_status_not_found_returns_404(self, client: TestClient):
        resp = client.get(
            "/api/v1/entities/ghost_entity/projection",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Auth header enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthHeader:

    def test_missing_authkey_returns_422(self, client: TestClient):
        """Requests without authkey header must be rejected."""
        resp = client.get("/api/v1/entities")
        # FastAPI returns 422 for missing required header
        assert resp.status_code == 422

    def test_present_authkey_passes(self, client: TestClient, sample_entity):
        resp = client.get("/api/v1/entities", headers={"authkey": "any-value"})
        assert resp.status_code == 200