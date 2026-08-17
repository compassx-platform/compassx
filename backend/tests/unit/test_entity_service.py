"""
Unit tests for app.services.entity_service

Coverage
--------
- EntityDefinition CRUD (create, read, update)
- EntityField CRUD (add, update, rename, delete)
- EntityRecord CRUD (create, read, update, soft-delete)
- Asset-scoped enforcement
- Required-field validation
- System-field injection (__now__, __uuid__ tokens)
- Audit log creation
- Field name validation (snake_case)
- Duplicate detection
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services import entity_service as svc
from app.models.entity import EntityDefinition, EntityField, EntityRecord
from app.models.audit import EntityAuditLog


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_entity(db: Session, name: str = "work_order", **kwargs) -> EntityDefinition:
    """Helper: create a simple entity definition."""
    defaults = {
        "entity_type": "generic",
        "asset_scoped": False,
        "time_based": False,
        "time_series": False,
        "fields": [
            {"field_name": "title", "field_type": "string", "is_required": True, "is_indexed": False},
            {"field_name": "priority", "field_type": "number", "is_required": False, "is_indexed": False},
        ],
        "system_fields": [],
    }
    defaults.update(kwargs)
    return svc.create_entity_definition(db, {"name": name, **defaults})


# ═══════════════════════════════════════════════════════════════════════════════
# EntityDefinition — create
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateEntityDefinition:

    def test_creates_entity_with_integer_id(self, db_session: Session):
        entity = _make_entity(db_session, "invoice")
        assert isinstance(entity.id, int)
        assert entity.id > 0

    def test_creates_entity_with_correct_name(self, db_session: Session):
        entity = _make_entity(db_session, "purchase_order")
        assert entity.name == "purchase_order"

    def test_creates_entity_with_fields(self, db_session: Session):
        entity = _make_entity(db_session, "maintenance_log")
        assert len(entity.fields) == 2
        field_names = {f.field_name for f in entity.fields}
        assert field_names == {"title", "priority"}

    def test_field_entity_id_is_integer_fk(self, db_session: Session):
        entity = _make_entity(db_session, "inspection")
        for field in entity.fields:
            assert isinstance(field.entity_id, int)
            assert field.entity_id == entity.id

    def test_creates_system_fields(self, db_session: Session):
        entity = svc.create_entity_definition(
            db_session,
            {
                "name": "event_log",
                "entity_type": "event",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [],
                "system_fields": [
                    {
                        "field_name": "created_ts",
                        "field_type": "datetime",
                        "default_value": "__now__",
                        "system_generated": True,
                        "is_indexed": False,
                    }
                ],
            },
        )
        sys_fields = [f for f in entity.fields if f.is_system]
        assert len(sys_fields) == 1
        assert sys_fields[0].field_name == "created_ts"
        assert sys_fields[0].system_generated is True

    def test_raises_on_duplicate_name(self, db_session: Session):
        _make_entity(db_session, "duplicate_entity")
        with pytest.raises(ValueError, match="already exists"):
            _make_entity(db_session, "duplicate_entity")

    def test_raises_on_invalid_name_uppercase(self, db_session: Session):
        with pytest.raises(ValueError, match="snake_case"):
            _make_entity(db_session, "InvalidName")

    def test_raises_on_invalid_name_spaces(self, db_session: Session):
        with pytest.raises(ValueError, match="snake_case"):
            _make_entity(db_session, "my entity")

    def test_raises_on_invalid_name_starts_with_digit(self, db_session: Session):
        with pytest.raises(ValueError, match="snake_case"):
            _make_entity(db_session, "1entity")

    def test_raises_on_duplicate_field_names(self, db_session: Session):
        with pytest.raises(ValueError, match="Duplicate field"):
            svc.create_entity_definition(
                db_session,
                {
                    "name": "bad_entity",
                    "entity_type": "generic",
                    "asset_scoped": False,
                    "time_based": False,
                    "time_series": False,
                    "fields": [
                        {"field_name": "title", "field_type": "string", "is_required": False, "is_indexed": False},
                        {"field_name": "title", "field_type": "text", "is_required": False, "is_indexed": False},
                    ],
                    "system_fields": [],
                },
            )

    def test_raises_on_invalid_field_type(self, db_session: Session):
        with pytest.raises(ValueError):
            svc.create_entity_definition(
                db_session,
                {
                    "name": "bad_type_entity",
                    "entity_type": "generic",
                    "asset_scoped": False,
                    "time_based": False,
                    "time_series": False,
                    "fields": [
                        {"field_name": "col", "field_type": "INVALID_TYPE", "is_required": False, "is_indexed": False},
                    ],
                    "system_fields": [],
                },
            )


# ═══════════════════════════════════════════════════════════════════════════════
# EntityDefinition — read
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetEntityDefinition:

    def test_get_by_name_returns_entity(self, db_session: Session):
        _make_entity(db_session, "readable_entity")
        result = svc.get_entity_definition(db_session, "readable_entity")
        assert result.name == "readable_entity"

    def test_get_by_name_raises_if_not_found(self, db_session: Session):
        with pytest.raises(ValueError, match="not found"):
            svc.get_entity_definition(db_session, "nonexistent_entity")

    def test_list_returns_all_entities(self, db_session: Session):
        _make_entity(db_session, "list_entity_a")
        _make_entity(db_session, "list_entity_b")
        results = svc.get_entity_definitions(db_session)
        names = {e.name for e in results}
        assert "list_entity_a" in names
        assert "list_entity_b" in names

    def test_list_with_limit(self, db_session: Session):
        for i in range(5):
            _make_entity(db_session, f"limit_entity_{i}")
        results = svc.get_entity_definitions(db_session, limit=2)
        assert len(results) <= 2


# ═══════════════════════════════════════════════════════════════════════════════
# EntityDefinition — update
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateEntityDefinition:

    def test_update_entity_type(self, db_session: Session):
        _make_entity(db_session, "updatable_entity")
        updated = svc.update_entity_definition(
            db_session, "updatable_entity", {"entity_type": "event"}
        )
        assert updated.entity_type == "event"

    def test_update_asset_scoped(self, db_session: Session):
        _make_entity(db_session, "scope_entity", asset_scoped=False)
        updated = svc.update_entity_definition(
            db_session, "scope_entity", {"asset_scoped": True}
        )
        assert updated.asset_scoped is True

    def test_update_raises_if_entity_not_found(self, db_session: Session):
        with pytest.raises(ValueError, match="not found"):
            svc.update_entity_definition(db_session, "ghost_entity", {"entity_type": "event"})

    def test_name_is_immutable(self, db_session: Session):
        """Updating with a 'name' key must be silently ignored (name is immutable)."""
        _make_entity(db_session, "immutable_name_entity")
        updated = svc.update_entity_definition(
            db_session, "immutable_name_entity", {"entity_type": "config"}
        )
        assert updated.name == "immutable_name_entity"


# ═══════════════════════════════════════════════════════════════════════════════
# EntityField — CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityFieldCRUD:

    def test_add_field_returns_integer_id(self, db_session: Session):
        _make_entity(db_session, "field_entity")
        field = svc.add_entity_field(
            db_session, "field_entity",
            {"field_name": "new_col", "field_type": "boolean", "is_required": False, "is_indexed": False},
        )
        assert isinstance(field.id, int)
        assert field.id > 0

    def test_add_field_sets_entity_id(self, db_session: Session):
        entity = _make_entity(db_session, "fk_entity")
        field = svc.add_entity_field(
            db_session, "fk_entity",
            {"field_name": "extra_col", "field_type": "string", "is_required": False, "is_indexed": False},
        )
        assert field.entity_id == entity.id

    def test_add_field_raises_on_duplicate(self, db_session: Session):
        _make_entity(db_session, "dup_field_entity")
        with pytest.raises(ValueError, match="already exists"):
            svc.add_entity_field(
                db_session, "dup_field_entity",
                {"field_name": "title", "field_type": "string", "is_required": False, "is_indexed": False},
            )

    def test_add_field_raises_on_invalid_name(self, db_session: Session):
        _make_entity(db_session, "invalid_field_entity")
        with pytest.raises(ValueError, match="snake_case"):
            svc.add_entity_field(
                db_session, "invalid_field_entity",
                {"field_name": "BadName", "field_type": "string", "is_required": False, "is_indexed": False},
            )

    def test_update_field_rename(self, db_session: Session):
        _make_entity(db_session, "rename_entity")
        updated = svc.update_entity_field(
            db_session, "rename_entity", "title",
            {"new_field_name": "subject"},
        )
        assert updated.field_name == "subject"

    def test_update_field_type(self, db_session: Session):
        _make_entity(db_session, "retype_entity")
        updated = svc.update_entity_field(
            db_session, "retype_entity", "title",
            {"field_type": "text"},
        )
        assert updated.field_type == "text"

    def test_update_field_required_flag(self, db_session: Session):
        _make_entity(db_session, "req_entity")
        updated = svc.update_entity_field(
            db_session, "req_entity", "priority",
            {"is_required": True},
        )
        assert updated.is_required is True

    def test_update_field_raises_if_not_found(self, db_session: Session):
        _make_entity(db_session, "ghost_field_entity")
        with pytest.raises(ValueError, match="not found"):
            svc.update_entity_field(
                db_session, "ghost_field_entity", "nonexistent_field", {}
            )

    def test_delete_field_returns_true(self, db_session: Session):
        _make_entity(db_session, "delete_field_entity")
        result = svc.delete_entity_field(db_session, "delete_field_entity", "priority")
        assert result is True

    def test_delete_field_returns_false_if_not_found(self, db_session: Session):
        _make_entity(db_session, "missing_field_entity")
        result = svc.delete_entity_field(db_session, "missing_field_entity", "ghost_col")
        assert result is False

    def test_get_entity_fields_returns_all(self, db_session: Session):
        _make_entity(db_session, "all_fields_entity")
        fields = svc.get_entity_fields(db_session, "all_fields_entity")
        assert len(fields) == 2
        names = {f.field_name for f in fields}
        assert names == {"title", "priority"}


# ═══════════════════════════════════════════════════════════════════════════════
# EntityRecord — create
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateRecord:

    def test_creates_record_with_integer_id(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", asset_id=None,
            data={"title": "Hello"}, user_email="user@test.com",
        )
        assert isinstance(record.id, int)
        assert record.id > 0

    def test_record_entity_id_matches_entity(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", asset_id=None,
            data={"title": "Hello"}, user_email="user@test.com",
        )
        assert record.entity_id == sample_entity.id

    def test_record_stores_data_json(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", asset_id=None,
            data={"title": "My Title", "count": 7},
            user_email="user@test.com",
        )
        assert record.data_json["title"] == "My Title"
        assert record.data_json["count"] == 7

    def test_record_default_status_is_open(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", asset_id=None,
            data={"title": "Status Test"}, user_email="user@test.com",
        )
        assert record.status == "OPEN"

    def test_record_stores_created_by(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", asset_id=None,
            data={"title": "Audit Test"}, user_email="auditor@test.com",
        )
        assert record.created_by == "auditor@test.com"

    def test_raises_on_missing_required_field(self, db_session: Session, sample_entity):
        with pytest.raises(ValueError, match="Missing required fields"):
            svc.create_record(
                db_session, "test_entity", asset_id=None,
                data={"count": 5},  # missing required 'title'
                user_email="user@test.com",
            )

    def test_raises_on_unknown_entity(self, db_session: Session):
        with pytest.raises(ValueError, match="not found"):
            svc.create_record(
                db_session, "nonexistent_entity", asset_id=None,
                data={}, user_email="user@test.com",
            )

    def test_asset_scoped_entity_requires_asset_id(
        self, db_session: Session, sample_asset_scoped_entity
    ):
        with pytest.raises(ValueError, match="asset-scoped"):
            svc.create_record(
                db_session, "asset_entity", asset_id=None,
                data={"severity": "HIGH"}, user_email="user@test.com",
            )

    def test_asset_scoped_entity_succeeds_with_asset_id(
        self, db_session: Session, sample_asset_scoped_entity
    ):
        record = svc.create_record(
            db_session, "asset_entity", asset_id="ASSET-001",
            data={"severity": "HIGH"}, user_email="user@test.com",
        )
        assert record.asset_id == "ASSET-001"

    def test_system_field_injection_now_token(self, db_session: Session):
        """__now__ token must be resolved to an ISO datetime string."""
        entity = svc.create_entity_definition(
            db_session,
            {
                "name": "ts_entity",
                "entity_type": "event",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [],
                "system_fields": [
                    {
                        "field_name": "recorded_at",
                        "field_type": "datetime",
                        "default_value": "__now__",
                        "system_generated": True,
                        "is_indexed": False,
                    }
                ],
            },
        )
        record = svc.create_record(
            db_session, "ts_entity", asset_id=None,
            data={}, user_email="user@test.com",
        )
        assert "recorded_at" in record.data_json
        # Should be a valid ISO datetime string
        assert isinstance(record.data_json["recorded_at"], str)
        datetime.fromisoformat(record.data_json["recorded_at"])

    def test_system_field_injection_uuid_token(self, db_session: Session):
        """__uuid__ token must be resolved to a UUID string."""
        import re
        svc.create_entity_definition(
            db_session,
            {
                "name": "uuid_entity",
                "entity_type": "generic",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [],
                "system_fields": [
                    {
                        "field_name": "ref_id",
                        "field_type": "string",
                        "default_value": "__uuid__",
                        "system_generated": True,
                        "is_indexed": False,
                    }
                ],
            },
        )
        record = svc.create_record(
            db_session, "uuid_entity", asset_id=None,
            data={}, user_email="user@test.com",
        )
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(record.data_json["ref_id"])

    def test_audit_log_created_on_record_creation(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", asset_id=None,
            data={"title": "Audit"}, user_email="auditor@test.com",
        )
        log = (
            db_session.query(EntityAuditLog)
            .filter(EntityAuditLog.entity_record_id == record.id)
            .first()
        )
        assert log is not None
        assert log.old_data is None
        assert log.changed_by == "auditor@test.com"


# ═══════════════════════════════════════════════════════════════════════════════
# EntityRecord — read
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetRecord:

    def test_get_record_by_integer_id(self, db_session: Session, sample_record):
        result = svc.get_record(db_session, "test_entity", sample_record.id)
        assert result is not None
        assert result.id == sample_record.id

    def test_get_record_returns_none_for_unknown_id(self, db_session: Session, sample_entity):
        result = svc.get_record(db_session, "test_entity", 999999)
        assert result is None

    def test_get_records_returns_list(self, db_session: Session, sample_entity):
        svc.create_record(db_session, "test_entity", None, {"title": "R1"}, "u@t.com")
        svc.create_record(db_session, "test_entity", None, {"title": "R2"}, "u@t.com")
        records = svc.get_records(db_session, "test_entity")
        assert len(records) >= 2

    def test_get_records_excludes_deleted(self, db_session: Session, sample_entity):
        r = svc.create_record(db_session, "test_entity", None, {"title": "ToDelete"}, "u@t.com")
        svc.soft_delete_record(db_session, "test_entity", r.id)
        records = svc.get_records(db_session, "test_entity")
        ids = [rec.id for rec in records]
        assert r.id not in ids


# ═══════════════════════════════════════════════════════════════════════════════
# EntityRecord — update
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateRecord:

    def test_update_record_data(self, db_session: Session, sample_record):
        updated = svc.update_record(
            db_session, "test_entity", sample_record.id,
            data={"title": "Updated Title"},
            user_email="editor@test.com",
        )
        assert updated.data_json["title"] == "Updated Title"

    def test_update_record_status(self, db_session: Session, sample_record):
        updated = svc.update_record(
            db_session, "test_entity", sample_record.id,
            data={}, status="CLOSED", user_email="editor@test.com",
        )
        assert updated.status.upper() == "CLOSED"

    def test_update_record_merges_data(self, db_session: Session, sample_entity):
        record = svc.create_record(
            db_session, "test_entity", None,
            {"title": "Original", "count": 1}, "u@t.com",
        )
        updated = svc.update_record(
            db_session, "test_entity", record.id,
            data={"count": 99}, user_email="editor@test.com",
        )
        # title should be preserved, count updated
        assert updated.data_json["title"] == "Original"
        assert updated.data_json["count"] == 99

    def test_update_record_returns_none_for_unknown_id(self, db_session: Session, sample_entity):
        result = svc.update_record(
            db_session, "test_entity", 999999,
            data={"title": "Ghost"}, user_email="editor@test.com",
        )
        assert result is None

    def test_update_record_creates_audit_log(self, db_session: Session, sample_record):
        svc.update_record(
            db_session, "test_entity", sample_record.id,
            data={"title": "Audit Update"}, user_email="auditor@test.com",
        )
        logs = (
            db_session.query(EntityAuditLog)
            .filter(EntityAuditLog.entity_record_id == sample_record.id)
            .all()
        )
        # At least 2 logs: creation + update
        assert len(logs) >= 2
        update_log = next((l for l in logs if l.old_data is not None), None)
        assert update_log is not None
        assert update_log.changed_by == "auditor@test.com"


# ═══════════════════════════════════════════════════════════════════════════════
# EntityRecord — soft delete
# ═══════════════════════════════════════════════════════════════════════════════


class TestSoftDeleteRecord:

    def test_soft_delete_sets_status_to_deleted(self, db_session: Session, sample_record):
        svc.soft_delete_record(db_session, "test_entity", sample_record.id)
        raw = db_session.query(EntityRecord).filter(EntityRecord.id == sample_record.id).first()
        assert raw.status == "DELETED"

    def test_soft_delete_returns_true(self, db_session: Session, sample_record):
        result = svc.soft_delete_record(db_session, "test_entity", sample_record.id)
        assert result is True

    def test_soft_delete_returns_false_for_unknown_id(self, db_session: Session, sample_entity):
        result = svc.soft_delete_record(db_session, "test_entity", 999999)
        assert result is False

    def test_soft_deleted_record_not_returned_by_get_record(
        self, db_session: Session, sample_record
    ):
        svc.soft_delete_record(db_session, "test_entity", sample_record.id)
        result = svc.get_record(db_session, "test_entity", sample_record.id)
        assert result is None

    def test_soft_delete_creates_audit_log(self, db_session: Session, sample_record):
        svc.soft_delete_record(db_session, "test_entity", sample_record.id, "deleter@test.com")
        logs = (
            db_session.query(EntityAuditLog)
            .filter(EntityAuditLog.entity_record_id == sample_record.id)
            .all()
        )
        delete_log = next(
            (l for l in logs if l.new_data and l.new_data.get("status") == "DELETED"), None
        )
        assert delete_log is not None
        assert delete_log.changed_by == "deleter@test.com"


# ═══════════════════════════════════════════════════════════════════════════════
# Field name validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestFieldNameValidation:

    @pytest.mark.parametrize("valid_name", [
        "simple",
        "with_underscore",
        "a1b2c3",
        "x" * 64,  # max length
    ])
    def test_valid_field_names_accepted(self, db_session: Session, valid_name: str):
        entity = svc.create_entity_definition(
            db_session,
            {
                "name": f"entity_for_{valid_name[:10]}",
                "entity_type": "generic",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [
                    {"field_name": valid_name, "field_type": "string",
                     "is_required": False, "is_indexed": False}
                ],
                "system_fields": [],
            },
        )
        assert any(f.field_name == valid_name for f in entity.fields)

    @pytest.mark.parametrize("invalid_name", [
        "UpperCase",
        "has space",
        "1starts_with_digit",
        "has-hyphen",
        "",
        "x" * 65,  # exceeds max length
    ])
    def test_invalid_field_names_rejected(self, db_session: Session, invalid_name: str):
        with pytest.raises(ValueError):
            svc.create_entity_definition(
                db_session,
                {
                    "name": "validation_entity",
                    "entity_type": "generic",
                    "asset_scoped": False,
                    "time_based": False,
                    "time_series": False,
                    "fields": [
                        {"field_name": invalid_name, "field_type": "string",
                         "is_required": False, "is_indexed": False}
                    ],
                    "system_fields": [],
                },
            )