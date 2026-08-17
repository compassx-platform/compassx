"""Dynamic projection service.

Creates and manages per-entity flat projection tables on demand.

Table naming convention:  {entity_name}_flat

Pipeline (enable_projection):
  1. create_projection_table  — DDL via raw SQL (CREATE TABLE IF NOT EXISTS)
  2. register_dynamic_handler — builds + registers a ProjectionHandler in the registry
  3. backfill_projection       — syncs all existing OPEN/CLOSED records into the new table

Auto-registration (auto_register_projections):
  Called at startup to re-register handlers for entities whose projection
  tables already exist (handlers are lost on process restart).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entity import EntityDefinition, EntityField, EntityRecord
from app.projections.base import ProjectionHandler
from app.services.projection_registry import get_handler, register

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────


def flat_table_name(entity_name: str) -> str:
    return f"{entity_name}_flat"


def _canonical_to_pg_type(canonical: str) -> str:
    return {
        "string":   "VARCHAR",
        "text":     "TEXT",
        "number":   "NUMERIC",
        "boolean":  "BOOLEAN",
        "time":     "TIME",
        "datetime": "TIMESTAMPTZ",
        "json":     "JSONB",
    }.get(canonical, "VARCHAR")


def _get_projection_fields(db: Session, entity_name: str) -> list[EntityField]:
    entity = db.query(EntityDefinition).filter(EntityDefinition.name == entity_name).first()
    if not entity:
        raise ValueError(f"Entity '{entity_name}' not found")
    return list(entity.fields)


def _expected_information_schema_type(canonical: str) -> str:
    return {
        "string": "character varying",
        "text": "text",
        "number": "numeric",
        "boolean": "boolean",
        "time": "time without time zone",
        "datetime": "timestamp with time zone",
        "json": "jsonb",
    }.get(canonical, "character varying")


def _quoted_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _json_serializable(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _alter_column_type_sql(table_name: str, column_name: str, canonical: str, existing_type: str) -> str:
    table_ident = _quoted_ident(table_name)
    col_ident = _quoted_ident(column_name)
    target_type = _canonical_to_pg_type(canonical)

    if canonical == "json":
        using_expr = (
            f"CASE WHEN {col_ident} IS NULL OR BTRIM({col_ident}::text) = '' "
            f"THEN NULL ELSE to_jsonb({col_ident}) END"
        )
    elif existing_type == "jsonb":
        using_expr = (
            f"CASE WHEN {col_ident} IS NULL THEN NULL "
            f"WHEN jsonb_typeof({col_ident}) = 'array' THEN NULLIF({col_ident}->>0, '')::{target_type} "
            f"ELSE NULLIF({col_ident} #>> '{{}}', '')::{target_type} END"
        )
    else:
        using_expr = (
            f"CASE WHEN {col_ident} IS NULL OR BTRIM({col_ident}::text) = '' "
            f"THEN NULL ELSE {col_ident}::{target_type} END"
        )

    return f"ALTER TABLE {table_ident} ALTER COLUMN {col_ident} TYPE {target_type} USING {using_expr}"


# ── Table existence ───────────────────────────────────────────────────────────


def _expected_sqlite_type(canonical: str) -> str:
    return {
        "string": "varchar",
        "text": "text",
        "number": "numeric",
        "boolean": "boolean",
        "time": "time",
        "datetime": "timestamptz",
        "json": "jsonb",
    }.get(canonical, "varchar")


def has_projection_table(db: Session, entity_name: str) -> bool:
    """Return True if the {entity_name}_flat table exists in the database."""
    tname = flat_table_name(entity_name)
    if db.bind.dialect.name == "sqlite":
        result = db.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:tname"),
            {"tname": tname},
        ).scalar()
        return bool(result)

    result = db.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = 'public' AND table_name = :tname"
            ")"
        ),
        {"tname": tname},
    ).scalar()
    return bool(result)


# ── DDL ───────────────────────────────────────────────────────────────────────


# Reserved column names that are always present as fixed columns.
# Entity fields with these names are skipped when building dynamic columns
# to avoid "column specified more than once" DDL errors.
_RESERVED_COLS = frozenset({"id", "record_id", "asset_id", "timestamp", "status", "created_by"})


def create_projection_table(db: Session, entity_name: str) -> None:
    """Create {entity_name}_flat if it does not already exist.

    Fixed columns:
        id          UUID PK
        record_id   UUID (unique — used for upsert)
        asset_id    VARCHAR
        timestamp   TIMESTAMPTZ
        status      VARCHAR
        created_by  VARCHAR

    Dynamic columns: one column per entity field whose name is
    NOT already in the fixed-column set.
    """
    tname = flat_table_name(entity_name)

    if has_projection_table(db, entity_name):
        logger.info("Projection table '%s' already exists — skipping DDL", tname)
        # Still sync schema in case new fields were added
        sync_projection_schema(db, entity_name)
        return

    fields = _get_projection_fields(db, entity_name)

    fixed_cols = [
        "id          SERIAL PRIMARY KEY" if db.bind.dialect.name != "sqlite" else "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "record_id   INTEGER NOT NULL",
        "asset_id    VARCHAR",           # nullable — non-asset-scoped entities have no asset_id
        "timestamp   TIMESTAMPTZ NOT NULL",
        "status      VARCHAR DEFAULT 'OPEN'",
        "created_by  VARCHAR",
    ]
    dynamic_cols = [
        f"{f.field_name}  {_canonical_to_pg_type(f.field_type)}"
        for f in fields
        if f.field_name not in _RESERVED_COLS
    ]
    all_cols = ",\n    ".join(fixed_cols + dynamic_cols)

    db.execute(text(f"CREATE TABLE IF NOT EXISTS {tname} (\n    {all_cols}\n)"))
    db.execute(text(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{entity_name}_flat_record_id "
        f"ON {tname} (record_id)"
    ))
    db.execute(text(
        f"CREATE INDEX IF NOT EXISTS idx_{entity_name}_flat_asset_time "
        f"ON {tname} (asset_id, timestamp)"
    ))
    db.execute(text(
        f"CREATE INDEX IF NOT EXISTS idx_{entity_name}_flat_status "
        f"ON {tname} (status)"
    ))
    db.commit()
    logger.info("Created projection table '%s' with %d dynamic columns", tname, len(dynamic_cols))


def sync_projection_schema(db: Session, entity_name: str) -> None:
    """Add columns for any entity fields not yet present in the flat table."""
    tname = flat_table_name(entity_name)
    if not has_projection_table(db, entity_name):
        return

    is_sqlite = db.bind.dialect.name == "sqlite"

    if is_sqlite:
        existing_cols = {
            row[1].lower(): row[2].lower()
            for row in db.execute(
                text(f"PRAGMA table_info({_quoted_ident(tname)})")
            ).fetchall()
        }
    else:
        existing_cols = {
            row[0]: row[1]
            for row in db.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :tname"
                ),
                {"tname": tname},
            )
        }

    fields = _get_projection_fields(db, entity_name)
    added = 0
    for f in fields:
        if f.field_name in _RESERVED_COLS:
            continue  # already a fixed column — skip
        if f.field_name not in existing_cols:
            pg_type = _canonical_to_pg_type(f.field_type)
            if is_sqlite:
                db.execute(text(
                    f'ALTER TABLE "{tname}" ADD COLUMN {f.field_name} {pg_type}'
                ))
            else:
                db.execute(text(
                    f"ALTER TABLE {tname} ADD COLUMN IF NOT EXISTS {f.field_name} {pg_type}"
                ))
            added += 1
            logger.info("Added column '%s' (%s) to '%s'", f.field_name, pg_type, tname)
            continue

        existing_type = existing_cols[f.field_name]
        expected_type = _expected_sqlite_type(f.field_type) if is_sqlite else _expected_information_schema_type(f.field_type)
        if existing_type != expected_type:
            db.execute(text(_alter_column_type_sql(tname, f.field_name, f.field_type, existing_type)))
            added += 1
            logger.info(
                "Updated column '%s' type on '%s' from %s to %s",
                f.field_name, tname, existing_type, expected_type,
            )

    if added:
        db.commit()


# ── Dynamic handler ───────────────────────────────────────────────────────────


class DynamicProjectionHandler(ProjectionHandler):
    """Generic upsert handler for any entity with a flat projection table."""

    def __init__(self, entity_name: str, field_types: dict[str, str]) -> None:
        self._entity_name = entity_name
        self._field_types = field_types
        self._tname = flat_table_name(entity_name)

    @property
    def entity_name(self) -> str:
        return self._entity_name

    def _bind_expression(self, field_name: str) -> str:
        if self._field_types.get(field_name) == "json":
            return f"CAST(:{field_name} AS JSONB)"
        return f":{field_name}"

    def sync(self, db: Session, record: EntityRecord) -> None:
        data: dict[str, Any] = record.data_json or {}

        # ── Soft delete ──────────────────────────────────────────────────────
        if record.status == "DELETED":
            db.execute(
                text(f"UPDATE {self._tname} SET status = 'DELETED' WHERE record_id = :rid"),
                {"rid": record.id},
            )
            return

        # ── Build row ────────────────────────────────────────────────────────
        row: dict[str, Any] = {
            "record_id":  record.id,
            "asset_id":   record.asset_id,
            "timestamp":  record.timestamp,
            "status":     record.status or "OPEN",
            "created_by": record.created_by,
        }
        # Only write dynamic fields that are NOT reserved fixed columns
        for fname, field_type in self._field_types.items():
            if fname not in _RESERVED_COLS:
                value = data.get(fname)
                row[fname] = _json_serializable(value) if field_type == "json" else value

        # ── Upsert ──────────────────────────────────────────────────────────
        exists = db.execute(
            text(f"SELECT 1 FROM {self._tname} WHERE record_id = :rid"),
            {"rid": record.id},
        ).scalar()

        if exists:
            set_clause = ", ".join(
                f"{k} = {self._bind_expression(k)}" for k in row if k != "record_id"
            )
            db.execute(
                text(f"UPDATE {self._tname} SET {set_clause} WHERE record_id = :record_id"),
                row,
            )
        else:
            cols = ", ".join(row.keys())
            vals = ", ".join(self._bind_expression(k) for k in row.keys())
            db.execute(
                text(f"INSERT INTO {self._tname} ({cols}) VALUES ({vals})"),
                row,
            )


def register_dynamic_handler(db: Session, entity_name: str, force: bool = False) -> None:
    """Build and register a DynamicProjectionHandler for *entity_name*."""
    if get_handler(entity_name) is not None and not force:
        logger.debug("Handler already registered for entity '%s'", entity_name)
        return
    fields = _get_projection_fields(db, entity_name)
    # Exclude reserved column names — they are written from record attributes, not data_json
    handler = DynamicProjectionHandler(
        entity_name,
        {f.field_name: f.field_type for f in fields if f.field_name not in _RESERVED_COLS},
    )
    register(handler)
    logger.info("Registered dynamic projection handler for entity '%s'", entity_name)


# ── Backfill ──────────────────────────────────────────────────────────────────


def backfill_projection(db: Session, entity_name: str) -> int:
    """Sync all non-deleted entity records into the projection table.

    Returns the number of records synced.
    """
    from app.services.projection_service import sync_projection

    entity = db.query(EntityDefinition).filter(EntityDefinition.name == entity_name).first()
    if not entity:
        raise ValueError(f"Entity '{entity_name}' not found")

    records: list[EntityRecord] = (
        db.query(EntityRecord)
        .filter(
            EntityRecord.entity_id == entity.id,
            EntityRecord.status != "DELETED",
        )
        .all()
    )

    for record in records:
        sync_projection(db, entity_name, record)

    db.commit()
    logger.info("Backfilled %d records into '%s'", len(records), flat_table_name(entity_name))
    return len(records)


# ── Full pipeline ─────────────────────────────────────────────────────────────


def enable_projection(db: Session, entity_name: str) -> dict:
    """Create table + register handler + backfill existing records."""
    create_projection_table(db, entity_name)
    register_dynamic_handler(db, entity_name)
    count = backfill_projection(db, entity_name)
    return {
        "entity_name":    entity_name,
        "table":          flat_table_name(entity_name),
        "records_synced": count,
        "enabled":        True,
    }


# ── Orphaned column management ───────────────────────────────────────────────


def get_orphaned_projection_columns(db: Session, entity_name: str) -> list[str]:
    """Return columns in the flat table that are NOT in entity_fields.

    These are columns left behind after form fields were deleted or renamed.
    Reserved fixed columns (id, record_id, asset_id, timestamp, status, created_by)
    are never considered orphaned.

    Returns an empty list if no projection table exists.
    """
    if not has_projection_table(db, entity_name):
        return []

    tname = flat_table_name(entity_name)
    is_sqlite = db.bind.dialect.name == "sqlite"

    if is_sqlite:
        all_cols = {
            row[1]
            for row in db.execute(
                text(f"PRAGMA table_info({_quoted_ident(tname)})")
            ).fetchall()
        }
    else:
        all_cols = {
            row[0]
            for row in db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :tname"
                ),
                {"tname": tname},
            )
        }

    # Columns that are still referenced by entity_fields
    fields = _get_projection_fields(db, entity_name)
    active_cols: set[str] = {f.field_name for f in fields}

    # Orphaned = in flat table, not reserved, not in entity_fields
    return sorted(
        col for col in all_cols
        if col not in _RESERVED_COLS and col not in active_cols
    )


def drop_projection_columns(db: Session, entity_name: str, columns: list[str]) -> list[str]:
    """Drop the specified columns from the flat projection table.

    Only non-reserved, non-active columns may be dropped (safety guard).
    Returns the list of columns actually dropped.

    WARNING: All data stored in these columns is permanently deleted.
    """
    if not has_projection_table(db, entity_name):
        raise ValueError(f"No projection table found for entity '{entity_name}'")

    tname = flat_table_name(entity_name)
    orphaned = set(get_orphaned_projection_columns(db, entity_name))
    dropped: list[str] = []
    is_sqlite = db.bind.dialect.name == "sqlite"

    for col in columns:
        if col in _RESERVED_COLS:
            logger.warning("drop_projection_columns: skipping reserved column '%s'", col)
            continue
        if col not in orphaned:
            logger.warning(
                "drop_projection_columns: skipping '%s' — not an orphaned column (still in entity_fields or does not exist)",
                col,
            )
            continue
        if is_sqlite:
            db.execute(text(f'ALTER TABLE "{tname}" DROP COLUMN "{col}"'))
        else:
            db.execute(text(f'ALTER TABLE "{tname}" DROP COLUMN IF EXISTS "{col}"'))
        dropped.append(col)
        logger.info("drop_projection_columns: dropped column '%s' from '%s'", col, tname)

    if dropped:
        db.commit()

    return dropped


# ── Startup auto-registration ─────────────────────────────────────────────────


def auto_register_projections(db: Session) -> None:
    """Re-register dynamic handlers for all entities that already have flat tables.

    Call this once at application startup so handlers survive process restarts.
    Skips entities that already have a registered handler (e.g. breakdown_event
    which is registered via static import).

    Each entity is processed independently so a single failure does not
    prevent other entities from being registered.
    """
    try:
        entities: list[EntityDefinition] = db.query(EntityDefinition).all()
    except Exception as exc:
        logger.error("auto_register_projections: failed to query entities — %s", exc)
        return

    registered = 0
    skipped = 0
    failed = 0

    for entity in entities:
        entity_name: str = entity.name  # EntityDefinition.name is the canonical identifier

        # Skip if already registered (static handler or previous call)
        if get_handler(entity_name) is not None:
            skipped += 1
            continue

        # Only register if a flat table actually exists
        try:
            if not has_projection_table(db, entity_name):
                continue
        except Exception as exc:
            logger.warning(
                "auto_register_projections: could not check table for entity '%s' — %s",
                entity_name, exc,
            )
            failed += 1
            continue

        try:
            fields = list(entity.fields)
            handler = DynamicProjectionHandler(
                entity_name,
                {f.field_name: f.field_type for f in fields if f.field_name not in _RESERVED_COLS},
            )
            register(handler)
            registered += 1
            logger.info(
                "auto_register_projections: registered handler for entity '%s'", entity_name
            )
        except Exception as exc:
            failed += 1
            logger.error(
                "auto_register_projections: failed to register handler for entity '%s' — %s",
                entity_name, exc,
            )

    logger.info(
        "auto_register_projections: done — registered=%d skipped=%d failed=%d",
        registered, skipped, failed,
    )
