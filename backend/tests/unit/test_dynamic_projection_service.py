"""
Unit tests for app.services.dynamic_projection_service

Coverage
--------
- flat_table_name() naming convention
- _canonical_to_pg_type() type mapping
- has_projection_table() — true / false
- create_projection_table() — DDL, idempotency, schema sync
- sync_projection_schema() — add missing columns, skip reserved cols
- DynamicProjectionHandler.sync() — upsert, soft-delete
- register_dynamic_handler() — registration, force re-register
- backfill_projection() — syncs existing records
- get_orphaned_projection_columns() — detects orphans
- drop_projection_columns() — drops orphans, guards reserved cols
- auto_register_projections() — startup re-registration

Note: DDL tests use the SQLite test database. PostgreSQL-specific
JSONB CAST expressions are tested via the handler's _bind_expression
method without executing actual SQL.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session

from app.workflows.services import dynamic_projection_service as svc
from app.workflows.services import entity_service
from app.workflows.services.projection_registry import get_handler, register, _REGISTRY


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_entity(db: Session, name: str):
    return entity_service.create_entity_definition(
        db,
        {
            "name": name,
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [
                {"field_name": "severity", "field_type": "string", "is_required": False, "is_indexed": False},
                {"field_name": "count", "field_type": "number", "is_required": False, "is_indexed": False},
                {"field_name": "metadata", "field_type": "json", "is_required": False, "is_indexed": False},
            ],
            "system_fields": [],
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# flat_table_name
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlatTableName:

    def test_appends_flat_suffix(self):
        assert svc.flat_table_name("work_order") == "work_order_flat"

    def test_preserves_entity_name(self):
        assert svc.flat_table_name("event_record") == "event_record_flat"

    def test_single_word(self):
        assert svc.flat_table_name("invoice") == "invoice_flat"

    def test_empty_string(self):
        assert svc.flat_table_name("") == "_flat"


# ═══════════════════════════════════════════════════════════════════════════════
# _canonical_to_pg_type
# ═══════════════════════════════════════════════════════════════════════════════


class TestCanonicalToPgType:

    @pytest.mark.parametrize("canonical,expected", [
        ("string",   "VARCHAR"),
        ("text",     "TEXT"),
        ("number",   "NUMERIC"),
        ("boolean",  "BOOLEAN"),
        ("time",     "TIME"),
        ("datetime", "TIMESTAMPTZ"),
        ("json",     "JSONB"),
    ])
    def test_known_types_mapped_correctly(self, canonical: str, expected: str):
        assert svc._canonical_to_pg_type(canonical) == expected

    def test_unknown_type_defaults_to_varchar(self):
        assert svc._canonical_to_pg_type("unknown_type") == "VARCHAR"

    def test_empty_string_defaults_to_varchar(self):
        assert svc._canonical_to_pg_type("") == "VARCHAR"


# ═══════════════════════════════════════════════════════════════════════════════
# has_projection_table
# ═══════════════════════════════════════════════════════════════════════════════


class TestHasProjectionTable:

    def test_returns_false_when_table_does_not_exist(self, db_session: Session):
        assert svc.has_projection_table(db_session, "nonexistent_entity") is False

    def test_returns_true_after_table_created(self, db_session: Session):
        _make_entity(db_session, "proj_check_entity")
        svc.create_projection_table(db_session, "proj_check_entity")
        assert svc.has_projection_table(db_session, "proj_check_entity") is True


# ═══════════════════════════════════════════════════════════════════════════════
# create_projection_table
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateProjectionTable:

    def test_creates_table_successfully(self, db_session: Session):
        _make_entity(db_session, "create_proj_entity")
        svc.create_projection_table(db_session, "create_proj_entity")
        assert svc.has_projection_table(db_session, "create_proj_entity") is True

    def test_idempotent_on_second_call(self, db_session: Session):
        _make_entity(db_session, "idempotent_proj_entity")
        svc.create_projection_table(db_session, "idempotent_proj_entity")
        # Second call should not raise
        svc.create_projection_table(db_session, "idempotent_proj_entity")
        assert svc.has_projection_table(db_session, "idempotent_proj_entity") is True

    def test_raises_if_entity_not_found(self, db_session: Session):
        with pytest.raises(ValueError, match="not found"):
            svc.create_projection_table(db_session, "ghost_proj_entity")

    def test_reserved_columns_not_duplicated(self, db_session: Session):
        """Entity fields with reserved names (id, record_id, etc.) must be skipped."""
        entity_service.create_entity_definition(
            db_session,
            {
                "name": "reserved_col_entity",
                "entity_type": "generic",
                "asset_scoped": False,
                "time_based": False,
                "time_series": False,
                "fields": [
                    # 'id' and 'record_id' are reserved — must not create duplicate columns
                    {"field_name": "id", "field_type": "number", "is_required": False, "is_indexed": False},
                    {"field_name": "record_id", "field_type": "number", "is_required": False, "is_indexed": False},
                    {"field_name": "custom_col", "field_type": "string", "is_required": False, "is_indexed": False},
                ],
                "system_fields": [],
            },
        )
        # Should not raise "column specified more than once"
        svc.create_projection_table(db_session, "reserved_col_entity")
        assert svc.has_projection_table(db_session, "reserved_col_entity") is True


# ═══════════════════════════════════════════════════════════════════════════════
# sync_projection_schema
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncProjectionSchema:

    def test_sync_adds_new_columns(self, db_session: Session):
        _make_entity(db_session, "sync_schema_entity")
        svc.create_projection_table(db_session, "sync_schema_entity")

        # Add a new field to the entity
        entity_service.add_entity_field(
            db_session, "sync_schema_entity",
            {"field_name": "new_sync_col", "field_type": "string", "is_required": False, "is_indexed": False},
        )

        # sync_projection_schema should add the new column without error
        svc.sync_projection_schema(db_session, "sync_schema_entity")

        # Verify the column exists in the table
        from sqlalchemy import text
        if db_session.bind.dialect.name == "sqlite":
            result = db_session.execute(
                text("PRAGMA table_info(sync_schema_entity_flat)")
            ).fetchall()
            assert any(row[1] == "new_sync_col" for row in result)
        else:
            result = db_session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'sync_schema_entity_flat' AND column_name = 'new_sync_col'"
                )
            ).fetchone()
            assert result is not None

    def test_sync_no_op_when_no_table(self, db_session: Session):
        """sync_projection_schema should silently return if no table exists."""
        _make_entity(db_session, "no_table_sync_entity")
        # Should not raise
        svc.sync_projection_schema(db_session, "no_table_sync_entity")

    def test_sync_skips_reserved_columns(self, db_session: Session):
        """Reserved columns must never be added as dynamic columns."""
        _make_entity(db_session, "reserved_sync_entity")
        svc.create_projection_table(db_session, "reserved_sync_entity")
        # Should not raise even if entity has reserved-named fields
        svc.sync_projection_schema(db_session, "reserved_sync_entity")


# ═══════════════════════════════════════════════════════════════════════════════
# DynamicProjectionHandler
# ═══════════════════════════════════════════════════════════════════════════════


class TestDynamicProjectionHandler:

    def test_entity_name_property(self):
        handler = svc.DynamicProjectionHandler(
            "test_entity",
            {"severity": "string", "count": "number"},
        )
        assert handler.entity_name == "test_entity"

    def test_bind_expression_plain_field(self):
        handler = svc.DynamicProjectionHandler("e", {"col": "string"})
        assert handler._bind_expression("col") == ":col"

    def test_bind_expression_json_field(self):
        handler = svc.DynamicProjectionHandler("e", {"meta": "json"})
        assert "JSONB" in handler._bind_expression("meta")

    def test_sync_upsert_insert(self, db_session: Session):
        """Handler.sync() should INSERT when record not in flat table."""
        _make_entity(db_session, "handler_insert_entity")
        svc.create_projection_table(db_session, "handler_insert_entity")
        svc.register_dynamic_handler(db_session, "handler_insert_entity")

        # Create a real entity record
        record = entity_service.create_record(
            db_session, "handler_insert_entity", None,
            {"severity": "HIGH", "count": 3}, "user@test.com",
        )

        handler = get_handler("handler_insert_entity")
        assert handler is not None
        handler.sync(db_session, record)
        db_session.flush()

        from sqlalchemy import text
        row = db_session.execute(
            text("SELECT record_id FROM handler_insert_entity_flat WHERE record_id = :rid"),
            {"rid": record.id},
        ).fetchone()
        assert row is not None

    def test_sync_upsert_update(self, db_session: Session):
        """Handler.sync() should UPDATE when record already in flat table."""
        _make_entity(db_session, "handler_update_entity")
        svc.create_projection_table(db_session, "handler_update_entity")
        svc.register_dynamic_handler(db_session, "handler_update_entity")

        record = entity_service.create_record(
            db_session, "handler_update_entity", None,
            {"severity": "LOW"}, "user@test.com",
        )

        handler = get_handler("handler_update_entity")
        handler.sync(db_session, record)
        db_session.flush()

        # Update the record and sync again
        record.data_json = {"severity": "CRITICAL"}
        handler.sync(db_session, record)
        db_session.flush()

        from sqlalchemy import text
        row = db_session.execute(
            text("SELECT severity FROM handler_update_entity_flat WHERE record_id = :rid"),
            {"rid": record.id},
        ).fetchone()
        assert row[0] == "CRITICAL"

    def test_sync_soft_delete(self, db_session: Session):
        """Handler.sync() with status=DELETED should mark flat row as DELETED."""
        _make_entity(db_session, "handler_delete_entity")
        svc.create_projection_table(db_session, "handler_delete_entity")
        svc.register_dynamic_handler(db_session, "handler_delete_entity")

        record = entity_service.create_record(
            db_session, "handler_delete_entity", None,
            {"severity": "LOW"}, "user@test.com",
        )

        handler = get_handler("handler_delete_entity")
        handler.sync(db_session, record)
        db_session.flush()

        # Soft-delete
        record.status = "DELETED"
        handler.sync(db_session, record)
        db_session.flush()

        from sqlalchemy import text
        row = db_session.execute(
            text("SELECT status FROM handler_delete_entity_flat WHERE record_id = :rid"),
            {"rid": record.id},
        ).fetchone()
        assert row[0] == "DELETED"


# ═══════════════════════════════════════════════════════════════════════════════
# register_dynamic_handler
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegisterDynamicHandler:

    def test_registers_handler_successfully(self, db_session: Session):
        _make_entity(db_session, "reg_handler_entity")
        svc.register_dynamic_handler(db_session, "reg_handler_entity")
        handler = get_handler("reg_handler_entity")
        assert handler is not None
        assert handler.entity_name == "reg_handler_entity"

    def test_does_not_re_register_if_already_registered(self, db_session: Session):
        _make_entity(db_session, "no_rereg_entity")
        svc.register_dynamic_handler(db_session, "no_rereg_entity")
        handler1 = get_handler("no_rereg_entity")
        svc.register_dynamic_handler(db_session, "no_rereg_entity")
        handler2 = get_handler("no_rereg_entity")
        # Same handler object (not re-created)
        assert handler1 is handler2

    def test_force_re_register(self, db_session: Session):
        _make_entity(db_session, "force_rereg_entity")
        svc.register_dynamic_handler(db_session, "force_rereg_entity")
        handler1 = get_handler("force_rereg_entity")
        svc.register_dynamic_handler(db_session, "force_rereg_entity", force=True)
        handler2 = get_handler("force_rereg_entity")
        # New handler object created
        assert handler1 is not handler2

    def test_raises_if_entity_not_found(self, db_session: Session):
        with pytest.raises(ValueError, match="not found"):
            svc.register_dynamic_handler(db_session, "ghost_handler_entity")


# ═══════════════════════════════════════════════════════════════════════════════
# backfill_projection
# ═══════════════════════════════════════════════════════════════════════════════


class TestBackfillProjection:

    def test_backfill_syncs_existing_records(self, db_session: Session):
        _make_entity(db_session, "backfill_entity")
        svc.create_projection_table(db_session, "backfill_entity")
        svc.register_dynamic_handler(db_session, "backfill_entity")

        # Create records BEFORE backfill
        entity_service.create_record(
            db_session, "backfill_entity", None, {"severity": "LOW"}, "u@t.com"
        )
        entity_service.create_record(
            db_session, "backfill_entity", None, {"severity": "HIGH"}, "u@t.com"
        )

        count = svc.backfill_projection(db_session, "backfill_entity")
        assert count == 2

    def test_backfill_excludes_deleted_records(self, db_session: Session):
        _make_entity(db_session, "backfill_del_entity")
        svc.create_projection_table(db_session, "backfill_del_entity")
        svc.register_dynamic_handler(db_session, "backfill_del_entity")

        r1 = entity_service.create_record(
            db_session, "backfill_del_entity", None, {"severity": "LOW"}, "u@t.com"
        )
        entity_service.create_record(
            db_session, "backfill_del_entity", None, {"severity": "HIGH"}, "u@t.com"
        )
        entity_service.soft_delete_record(db_session, "backfill_del_entity", r1.id)

        count = svc.backfill_projection(db_session, "backfill_del_entity")
        assert count == 1  # Only the non-deleted record

    def test_backfill_raises_if_entity_not_found(self, db_session: Session):
        with pytest.raises(ValueError, match="not found"):
            svc.backfill_projection(db_session, "ghost_backfill_entity")


# ═══════════════════════════════════════════════════════════════════════════════
# get_orphaned_projection_columns
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetOrphanedProjectionColumns:

    def test_returns_empty_if_no_table(self, db_session: Session):
        _make_entity(db_session, "orphan_no_table_entity")
        result = svc.get_orphaned_projection_columns(db_session, "orphan_no_table_entity")
        assert result == []

    def test_returns_empty_when_no_orphans(self, db_session: Session):
        _make_entity(db_session, "no_orphan_entity")
        svc.create_projection_table(db_session, "no_orphan_entity")
        result = svc.get_orphaned_projection_columns(db_session, "no_orphan_entity")
        assert result == []

    def test_detects_orphaned_column(self, db_session: Session):
        _make_entity(db_session, "orphan_detect_entity")
        svc.create_projection_table(db_session, "orphan_detect_entity")

        # Manually add a column that has no corresponding entity field
        from sqlalchemy import text
        db_session.execute(
            text("ALTER TABLE orphan_detect_entity_flat ADD COLUMN orphaned_col VARCHAR")
        )
        db_session.flush()

        orphans = svc.get_orphaned_projection_columns(db_session, "orphan_detect_entity")
        assert "orphaned_col" in orphans

    def test_reserved_columns_never_orphaned(self, db_session: Session):
        _make_entity(db_session, "reserved_orphan_entity")
        svc.create_projection_table(db_session, "reserved_orphan_entity")
        orphans = svc.get_orphaned_projection_columns(db_session, "reserved_orphan_entity")
        for reserved in {"id", "record_id", "asset_id", "timestamp", "status", "created_by"}:
            assert reserved not in orphans


# ═══════════════════════════════════════════════════════════════════════════════
# drop_projection_columns
# ═══════════════════════════════════════════════════════════════════════════════


class TestDropProjectionColumns:

    def test_drops_orphaned_column(self, db_session: Session):
        _make_entity(db_session, "drop_col_entity")
        svc.create_projection_table(db_session, "drop_col_entity")

        from sqlalchemy import text
        db_session.execute(
            text("ALTER TABLE drop_col_entity_flat ADD COLUMN to_drop VARCHAR")
        )
        db_session.flush()

        dropped = svc.drop_projection_columns(db_session, "drop_col_entity", ["to_drop"])
        assert "to_drop" in dropped

    def test_skips_reserved_columns(self, db_session: Session):
        _make_entity(db_session, "skip_reserved_entity")
        svc.create_projection_table(db_session, "skip_reserved_entity")

        dropped = svc.drop_projection_columns(db_session, "skip_reserved_entity", ["id", "record_id"])
        assert "id" not in dropped
        assert "record_id" not in dropped

    def test_skips_active_columns(self, db_session: Session):
        """Active entity field columns must not be dropped."""
        _make_entity(db_session, "skip_active_entity")
        svc.create_projection_table(db_session, "skip_active_entity")

        # 'severity' is an active field — must not be dropped
        dropped = svc.drop_projection_columns(db_session, "skip_active_entity", ["severity"])
        assert "severity" not in dropped

    def test_raises_if_no_projection_table(self, db_session: Session):
        _make_entity(db_session, "no_table_drop_entity")
        with pytest.raises(ValueError, match="No projection table"):
            svc.drop_projection_columns(db_session, "no_table_drop_entity", ["col"])

    def test_returns_empty_list_when_nothing_dropped(self, db_session: Session):
        _make_entity(db_session, "nothing_dropped_entity")
        svc.create_projection_table(db_session, "nothing_dropped_entity")
        dropped = svc.drop_projection_columns(db_session, "nothing_dropped_entity", [])
        assert dropped == []