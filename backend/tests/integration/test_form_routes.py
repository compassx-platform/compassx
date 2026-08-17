"""
Integration tests for form API routes

Coverage
--------
- POST   /api/v1/forms                  — create form
- GET    /api/v1/forms                  — list forms
- GET    /api/v1/forms/{form_id}        — get form
- PUT    /api/v1/forms/{form_id}        — update form
- DELETE /api/v1/forms/{form_id}        — delete form
- POST   /api/v1/forms/{form_id}/submit — submit form record
- GET    /api/v1/forms/{form_id}/template — download CSV template
- POST   /api/v1/forms/{form_id}/bulk-upload — bulk upload CSV
- HTTP 404 / 422 error responses
"""

from __future__ import annotations

import io
import csv
import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _build_csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# Form CRUD Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateFormRoute:

    def test_create_form_returns_201(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/forms",
            json={
                "form_id": "route-form-001",
                "entity_name": "test_entity",
                "schema": {
                    "fields": [
                        {"id": "title", "type": "text", "label": "Title", "required": True}
                    ]
                },
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201

    def test_create_form_returns_integer_id(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/forms",
            json={
                "form_id": "int-id-form",
                "entity_name": "test_entity",
                "schema": {"fields": []},
            },
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_create_form_returns_correct_form_id(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/forms",
            json={
                "form_id": "correct-form-id",
                "entity_name": "test_entity",
                "schema": {"fields": []},
            },
            headers={"authkey": "test-key"},
        )
        assert resp.json()["form_id"] == "correct-form-id"

    def test_create_form_entity_not_found_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/forms",
            json={
                "form_id": "orphan-form",
                "entity_name": "nonexistent_entity",
                "schema": {"fields": []},
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_create_form_missing_form_id_returns_422(self, client: TestClient, sample_entity):
        resp = client.post(
            "/api/v1/forms",
            json={"entity_name": "test_entity", "schema": {}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422

    def test_create_form_missing_entity_name_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/forms",
            json={"form_id": "no-entity-form", "schema": {}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422


class TestListFormsRoute:

    def test_list_forms_returns_200(self, client: TestClient, sample_form):
        resp = client.get("/api/v1/forms", headers={"authkey": "test-key"})
        assert resp.status_code == 200

    def test_list_forms_returns_list(self, client: TestClient, sample_form):
        resp = client.get("/api/v1/forms", headers={"authkey": "test-key"})
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_forms_contains_created_form(self, client: TestClient, sample_form):
        resp = client.get("/api/v1/forms", headers={"authkey": "test-key"})
        form_ids = [f["form_id"] for f in resp.json()]
        assert "test-form-001" in form_ids

    def test_list_forms_have_integer_ids(self, client: TestClient, sample_form):
        resp = client.get("/api/v1/forms", headers={"authkey": "test-key"})
        for form in resp.json():
            assert isinstance(form["id"], int)


class TestGetFormRoute:

    def test_get_form_returns_200(self, client: TestClient, sample_form):
        resp = client.get("/api/v1/forms/test-form-001", headers={"authkey": "test-key"})
        assert resp.status_code == 200

    def test_get_form_returns_correct_form_id(self, client: TestClient, sample_form):
        resp = client.get("/api/v1/forms/test-form-001", headers={"authkey": "test-key"})
        assert resp.json()["form_id"] == "test-form-001"

    def test_get_form_not_found_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/forms/nonexistent-form", headers={"authkey": "test-key"})
        assert resp.status_code == 404


class TestUpdateFormRoute:

    def test_update_form_returns_200(self, client: TestClient, sample_form):
        resp = client.put(
            "/api/v1/forms/test-form-001",
            json={
                "schema": {
                    "fields": [
                        {"id": "title", "type": "text", "label": "Title", "required": True},
                        {"id": "status", "type": "select", "label": "Status", "required": False},
                    ]
                }
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_update_form_changes_schema(self, client: TestClient, sample_form):
        resp = client.put(
            "/api/v1/forms/test-form-001",
            json={
                "schema": {
                    "fields": [
                        {"id": "updated_field", "type": "text", "label": "Updated", "required": False}
                    ]
                }
            },
            headers={"authkey": "test-key"},
        )
        schema = resp.json().get("schema", {})
        field_ids = [f["id"] for f in schema.get("fields", [])]
        assert "updated_field" in field_ids

    def test_update_form_not_found_returns_404(self, client: TestClient):
        resp = client.put(
            "/api/v1/forms/ghost-form",
            json={"schema": {"fields": []}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_update_form_invalid_entity_returns_404(self, client: TestClient, sample_form):
        resp = client.put(
            "/api/v1/forms/test-form-001",
            json={"entity_name": "nonexistent_entity"},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404


class TestDeleteFormRoute:

    def test_delete_form_returns_204(self, client: TestClient, sample_entity):
        # Create a form to delete
        client.post(
            "/api/v1/forms",
            json={
                "form_id": "form-to-delete",
                "entity_name": "test_entity",
                "schema": {"fields": []},
            },
            headers={"authkey": "test-key"},
        )
        resp = client.delete("/api/v1/forms/form-to-delete", headers={"authkey": "test-key"})
        assert resp.status_code == 204

    def test_delete_form_removes_from_list(self, client: TestClient, sample_entity):
        client.post(
            "/api/v1/forms",
            json={
                "form_id": "form-to-delete-2",
                "entity_name": "test_entity",
                "schema": {"fields": []},
            },
            headers={"authkey": "test-key"},
        )
        client.delete("/api/v1/forms/form-to-delete-2", headers={"authkey": "test-key"})
        resp = client.get("/api/v1/forms", headers={"authkey": "test-key"})
        form_ids = [f["form_id"] for f in resp.json()]
        assert "form-to-delete-2" not in form_ids

    def test_delete_form_not_found_returns_404(self, client: TestClient):
        resp = client.delete("/api/v1/forms/nonexistent-form", headers={"authkey": "test-key"})
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Form Submit Route
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormSubmitRoute:

    def test_submit_form_returns_201(self, client: TestClient, sample_form, sample_entity):
        resp = client.post(
            "/api/v1/forms/test-form-001/submit",
            json={
                "asset_id": "ASSET-001",
                "data": {"title": "Submitted Record"},
            },
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 201

    def test_submit_form_returns_integer_record_id(
        self, client: TestClient, sample_form, sample_entity
    ):
        resp = client.post(
            "/api/v1/forms/test-form-001/submit",
            json={"data": {"title": "ID Test"}},
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert isinstance(data["id"], int)

    def test_submit_form_not_found_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/v1/forms/ghost-form/submit",
            json={"data": {"title": "Test"}},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_submit_form_missing_required_field_returns_422(
        self, client: TestClient, sample_form, sample_entity
    ):
        resp = client.post(
            "/api/v1/forms/test-form-001/submit",
            json={"data": {}},  # missing required 'title'
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# CSV Template Route
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormTemplateRoute:

    def test_get_template_returns_200(self, client: TestClient, sample_form):
        resp = client.get(
            "/api/v1/forms/test-form-001/template",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_get_template_returns_csv_content_type(self, client: TestClient, sample_form):
        resp = client.get(
            "/api/v1/forms/test-form-001/template",
            headers={"authkey": "test-key"},
        )
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_get_template_not_found_returns_404(self, client: TestClient):
        resp = client.get(
            "/api/v1/forms/ghost-form/template",
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_get_template_has_header_row(self, client: TestClient, sample_form):
        resp = client.get(
            "/api/v1/forms/test-form-001/template",
            headers={"authkey": "test-key"},
        )
        content = resp.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) >= 1
        assert "asset_id" in rows[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Bulk Upload Route
# ═══════════════════════════════════════════════════════════════════════════════


class TestBulkUploadRoute:

    def test_bulk_upload_preview_returns_200(
        self, client: TestClient, sample_form, sample_entity
    ):
        csv_bytes = _build_csv_bytes([
            ["asset_id", "Title", "Count"],
            ["ASSET-001", "Row 1", "10"],
            ["ASSET-002", "Row 2", "20"],
        ])
        resp = client.post(
            "/api/v1/forms/test-form-001/bulk-upload",
            files={"file": ("upload.csv", csv_bytes, "text/csv")},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 200

    def test_bulk_upload_preview_returns_row_count(
        self, client: TestClient, sample_form, sample_entity
    ):
        csv_bytes = _build_csv_bytes([
            ["asset_id", "Title"],
            ["A1", "Row 1"],
            ["A2", "Row 2"],
            ["A3", "Row 3"],
        ])
        resp = client.post(
            "/api/v1/forms/test-form-001/bulk-upload",
            files={"file": ("upload.csv", csv_bytes, "text/csv")},
            headers={"authkey": "test-key"},
        )
        data = resp.json()
        assert "rows" in data or "row_count" in data

    def test_bulk_upload_form_not_found_returns_404(self, client: TestClient):
        csv_bytes = _build_csv_bytes([["asset_id", "Title"], ["A1", "Row 1"]])
        resp = client.post(
            "/api/v1/forms/ghost-form/bulk-upload",
            files={"file": ("upload.csv", csv_bytes, "text/csv")},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code == 404

    def test_bulk_commit_returns_201(
        self, client: TestClient, sample_form, sample_entity
    ):
        csv_bytes = _build_csv_bytes([
            ["asset_id", "Title"],
            ["A1", "Committed Row"],
        ])
        resp = client.post(
            "/api/v1/forms/test-form-001/bulk-upload?commit=true",
            files={"file": ("upload.csv", csv_bytes, "text/csv")},
            headers={"authkey": "test-key"},
        )
        assert resp.status_code in (200, 201)