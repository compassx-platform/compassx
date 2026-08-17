"""
Unit tests for app.services.form_service

Coverage
--------
- Form CRUD (create, read, update, delete)
- Entity-must-exist enforcement
- Field sync from form to entity
- Bulk upload CSV/Excel parsing
- Bulk upload commit (record creation, validation)
- Template generation (CSV)
"""

from __future__ import annotations

import io
import csv
import pytest
from sqlalchemy.orm import Session

from app.services import form_service as svc
from app.services import entity_service
from app.schemas.form import FormSchemaCreate, FormSchemaUpdate
from app.models.form import Form
from app.models.entity import EntityRecord


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_entity(db: Session, name: str = "form_entity"):
    return entity_service.create_entity_definition(
        db,
        {
            "name": name,
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [
                {"field_name": "title", "field_type": "string", "is_required": True, "is_indexed": False},
                {"field_name": "notes", "field_type": "text", "is_required": False, "is_indexed": False},
            ],
            "system_fields": [],
        },
    )


def _make_form(db: Session, entity_name: str = "form_entity", form_id: str = "form-001") -> Form:
    return svc.create_form_schema(
        db,
        FormSchemaCreate(
            form_id=form_id,
            entity_name=entity_name,
            schema={
                "form_id": form_id,
                "entity": entity_name,
                "fields": [
                    {"id": "title", "type": "text", "label": "Title", "required": True},
                    {"id": "notes", "type": "textarea", "label": "Notes", "required": False},
                ],
            },
        ),
    )


def _build_csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# Form CRUD — create
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateFormSchema:

    def test_creates_form_with_integer_id(self, db_session: Session):
        _make_entity(db_session, "create_form_entity")
        form = _make_form(db_session, "create_form_entity", "form-create-001")
        assert isinstance(form.id, int)
        assert form.id > 0

    def test_creates_form_with_correct_form_id(self, db_session: Session):
        _make_entity(db_session, "form_id_entity")
        form = _make_form(db_session, "form_id_entity", "my-unique-form")
        assert form.form_id == "my-unique-form"

    def test_creates_form_with_entity_name(self, db_session: Session):
        _make_entity(db_session, "entity_name_form_entity")
        form = _make_form(db_session, "entity_name_form_entity", "form-ename-001")
        assert form.entity_name == "entity_name_form_entity"

    def test_raises_if_entity_does_not_exist(self, db_session: Session):
        with pytest.raises(ValueError, match="does not exist"):
            svc.create_form_schema(
                db_session,
                FormSchemaCreate(
                    form_id="orphan-form",
                    entity_name="nonexistent_entity",
                    schema={"fields": []},
                ),
            )

    def test_form_fields_synced_to_entity(self, db_session: Session):
        """New form fields should be synced back to entity_fields."""
        _make_entity(db_session, "sync_entity")
        # Add a new field via form that doesn't exist on entity
        svc.create_form_schema(
            db_session,
            FormSchemaCreate(
                form_id="sync-form-001",
                entity_name="sync_entity",
                schema={
                    "fields": [
                        {"id": "title", "type": "text", "label": "Title", "required": True},
                        {"id": "new_field", "type": "text", "label": "New Field", "required": False},
                    ]
                },
            ),
        )
        fields = entity_service.get_entity_fields(db_session, "sync_entity")
        field_names = {f.field_name for f in fields}
        assert "new_field" in field_names


# ═══════════════════════════════════════════════════════════════════════════════
# Form CRUD — read
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetFormSchema:

    def test_get_form_by_form_id(self, db_session: Session, sample_form):
        result = svc.get_form_schema(db_session, "test-form-001")
        assert result is not None
        assert result.form_id == "test-form-001"

    def test_get_form_returns_none_if_not_found(self, db_session: Session):
        result = svc.get_form_schema(db_session, "nonexistent-form")
        assert result is None

    def test_get_forms_returns_list(self, db_session: Session, sample_form):
        forms = svc.get_forms(db_session)
        assert len(forms) >= 1
        form_ids = {f.form_id for f in forms}
        assert "test-form-001" in form_ids


# ═══════════════════════════════════════════════════════════════════════════════
# Form CRUD — update
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateFormSchema:

    def test_update_form_schema_fields(self, db_session: Session, sample_form):
        updated = svc.update_form_schema(
            db_session,
            "test-form-001",
            FormSchemaUpdate(
                schema={
                    "fields": [
                        {"id": "title", "type": "text", "label": "Title", "required": True},
                        {"id": "count", "type": "number", "label": "Count", "required": False},
                        {"id": "status", "type": "select", "label": "Status", "required": False},
                    ]
                }
            ),
        )
        assert updated is not None
        fields = updated.schema.get("fields", [])
        field_ids = {f["id"] for f in fields}
        assert "status" in field_ids

    def test_update_returns_none_if_form_not_found(self, db_session: Session):
        result = svc.update_form_schema(
            db_session, "ghost-form", FormSchemaUpdate(schema={"fields": []})
        )
        assert result is None

    def test_update_raises_if_new_entity_does_not_exist(self, db_session: Session, sample_form):
        with pytest.raises(ValueError, match="does not exist"):
            svc.update_form_schema(
                db_session,
                "test-form-001",
                FormSchemaUpdate(entity_name="nonexistent_entity"),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Form CRUD — delete
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteFormSchema:

    def test_delete_form_returns_true(self, db_session: Session):
        _make_entity(db_session, "del_form_entity")
        _make_form(db_session, "del_form_entity", "form-to-delete")
        result = svc.delete_form_schema(db_session, "form-to-delete")
        assert result is True

    def test_delete_form_removes_from_db(self, db_session: Session):
        _make_entity(db_session, "del_form_entity2")
        _make_form(db_session, "del_form_entity2", "form-to-delete-2")
        svc.delete_form_schema(db_session, "form-to-delete-2")
        result = svc.get_form_schema(db_session, "form-to-delete-2")
        assert result is None

    def test_delete_form_returns_false_if_not_found(self, db_session: Session):
        result = svc.delete_form_schema(db_session, "nonexistent-form-id")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Bulk upload — CSV parsing
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseBulkUpload:

    def test_parse_csv_returns_rows(self, db_session: Session, sample_form):
        csv_bytes = _build_csv([
            ["asset_id", "Title", "Count"],
            ["ASSET-001", "First Record", "10"],
            ["ASSET-002", "Second Record", "20"],
        ])
        result = svc.parse_bulk_upload(sample_form, csv_bytes, "upload.csv")
        assert len(result["rows"]) == 2

    def test_parse_csv_maps_headers_to_field_ids(self, db_session: Session, sample_form):
        csv_bytes = _build_csv([
            ["asset_id", "Title", "Count"],
            ["ASSET-001", "My Title", "5"],
        ])
        result = svc.parse_bulk_upload(sample_form, csv_bytes, "upload.csv")
        row = result["rows"][0]
        assert row.get("asset_id") == "ASSET-001"

    def test_parse_csv_skips_hint_row(self, db_session: Session, sample_form):
        """Second row that looks like a hint row should be skipped."""
        csv_bytes = _build_csv([
            ["asset_id", "Title", "Count"],
            ["Asset identifier", "text [required]", "number"],  # hint row
            ["ASSET-001", "Real Data", "7"],
        ])
        result = svc.parse_bulk_upload(sample_form, csv_bytes, "upload.csv")
        # Only 1 data row (hint row skipped)
        assert len(result["rows"]) == 1

    def test_parse_csv_returns_errors_for_missing_required_fields(
        self, db_session: Session, sample_form
    ):
        csv_bytes = _build_csv([
            ["asset_id", "Title", "Count"],
            ["ASSET-001", "", "5"],  # missing required Title
        ])
        result = svc.parse_bulk_upload(sample_form, csv_bytes, "upload.csv")
        assert len(result["errors"]) > 0

    def test_parse_empty_csv_returns_error(self, db_session: Session, sample_form):
        result = svc.parse_bulk_upload(sample_form, b"", "upload.csv")
        assert len(result["errors"]) > 0

    def test_parse_csv_returns_field_metadata(self, db_session: Session, sample_form):
        csv_bytes = _build_csv([["asset_id", "Title"]])
        result = svc.parse_bulk_upload(sample_form, csv_bytes, "upload.csv")
        assert "fields" in result
        assert isinstance(result["fields"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# Bulk upload — commit rows
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommitBulkRows:

    def test_commit_creates_entity_records(self, db_session: Session, sample_form, sample_entity):
        rows = [
            {"_row": 3, "asset_id": "A1", "title": "Row 1", "count": "10"},
            {"_row": 4, "asset_id": "A2", "title": "Row 2", "count": "20"},
        ]
        result = svc.commit_bulk_rows(db_session, sample_form, rows, "bulk@test.com")
        assert result["created"] == 2
        assert len(result["errors"]) == 0

    def test_commit_returns_errors_for_missing_required_fields(
        self, db_session: Session, sample_form, sample_entity
    ):
        rows = [
            {"_row": 3, "asset_id": "A1", "title": "", "count": "10"},  # missing required title
        ]
        result = svc.commit_bulk_rows(db_session, sample_form, rows, "bulk@test.com")
        assert result["created"] == 0
        assert len(result["errors"]) == 1

    def test_commit_returns_error_if_entity_missing(self, db_session: Session):
        """If the entity referenced by the form no longer exists, commit should fail gracefully."""
        orphan_form = Form(
            form_id="orphan-bulk-form",
            entity_name="deleted_entity",
            schema={"fields": [{"id": "title", "type": "text", "label": "Title", "required": True}]},
        )
        db_session.add(orphan_form)
        db_session.flush()
        rows = [{"_row": 3, "asset_id": "A1", "title": "Test"}]
        result = svc.commit_bulk_rows(db_session, orphan_form, rows, "bulk@test.com")
        assert result["created"] == 0
        assert len(result["errors"]) > 0

    def test_commit_sets_created_by(self, db_session: Session, sample_form, sample_entity):
        rows = [{"_row": 3, "asset_id": "A1", "title": "Row 1"}]
        svc.commit_bulk_rows(db_session, sample_form, rows, "bulk_user@test.com")
        record = (
            db_session.query(EntityRecord)
            .filter(EntityRecord.entity_id == sample_entity.id)
            .first()
        )
        assert record is not None
        assert record.created_by == "bulk_user@test.com"

    def test_commit_partial_success(self, db_session: Session, sample_form, sample_entity):
        """Valid rows should be committed even if some rows have errors."""
        rows = [
            {"_row": 3, "asset_id": "A1", "title": "Valid Row"},
            {"_row": 4, "asset_id": "A2", "title": ""},  # missing required
        ]
        result = svc.commit_bulk_rows(db_session, sample_form, rows, "bulk@test.com")
        assert result["created"] == 1
        assert len(result["errors"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Template generation
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateTemplate:

    def test_generate_csv_template_returns_bytes(self, db_session: Session, sample_form):
        result = svc.generate_bulk_template_csv(sample_form)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_csv_template_has_header_row(self, db_session: Session, sample_form):
        result = svc.generate_bulk_template_csv(sample_form)
        text = result.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        assert len(rows) >= 1
        header = rows[0]
        assert "asset_id" in header

    def test_generate_csv_template_includes_all_field_labels(
        self, db_session: Session, sample_form
    ):
        result = svc.generate_bulk_template_csv(sample_form)
        text = result.decode("utf-8-sig")
        # Template should contain field labels
        assert "Title" in text or "title" in text.lower()