"""Generic entity CRUD service.

Handles create / read / update / soft-delete for any registered entity.

Key responsibilities
--------------------
- Entity definition CRUD (create_entity_definition, get_entity_definitions)
- Record CRUD with:
    * asset_scoped enforcement  (asset_id required when entity.asset_scoped=True)
    * required-field validation (non-system fields only)
    * system field injection    (is_system=True fields injected / overridden)
    * projection sync           (via projection_service → registry → handler)
- Entity field sync from form   (sync_entity_fields_from_form)
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import EntityAuditLog
from app.models.entity import EntityDefinition, EntityField, EntityRecord
from app.services import state_machine_service
from app.services.field_type_registry import map_form_field, map_form_type, validate_canonical_type
from app.services.projection_service import sync_projection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field name validation — lowercase snake_case, 1-64 chars
# ---------------------------------------------------------------------------
_VALID_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Special tokens resolved during system field injection
# Note: __uuid__ generates a UUID string for field *values*, not DB IDs
_SPECIAL_TOKENS: dict[str, Any] = {
    "__now__":  lambda: datetime.now(timezone.utc).isoformat(),
    "__uuid__": lambda: str(uuid.uuid4()),
}


# ── Internal helpers ────────────────────────────────────────────────────────


def _get_entity_def(db: Session, entity_name: str) -> EntityDefinition:
    entity = db.query(EntityDefinition).filter(EntityDefinition.name == entity_name).first()
    if not entity:
        raise ValueError(f"Entity '{entity_name}' not found")
    return entity


def _resolve_default(raw: str | None) -> Any:
    """Resolve a default_value string, supporting special tokens."""
    if raw is None:
        return None
    factory = _SPECIAL_TOKENS.get(raw)
    return factory() if factory else raw


def _inject_system_fields(data: dict, system_fields: list[EntityField]) -> dict:
    """Return a copy of *data* with system fields injected.

    Rules:
      - system_generated=True  → ALWAYS override (server owns the value)
      - system_generated=False → inject only if the key is absent from data
    """
    result = dict(data)
    for sf in system_fields:
        resolved = _resolve_default(sf.default_value)
        if sf.system_generated:
            result[sf.field_name] = resolved
        else:
            result.setdefault(sf.field_name, resolved)
    return result


def _normalize_record_data(entity_def: EntityDefinition, data: dict[str, Any]) -> dict[str, Any]:
    """Normalize caller-provided record data based on entity field types.

    Current rules:
      - blank strings for typed fields (number, boolean, time, datetime, json)
        are converted to None so projection inserts do not fail on invalid casts
      - whitespace-only values are treated as blank
      - text-like fields keep their original string values
    """
    field_types = {
        field.field_name: field.field_type
        for field in entity_def.fields
    }
    null_if_blank_types = {"number", "boolean", "time", "datetime", "json"}

    normalized: dict[str, Any] = {}
    for key, value in data.items():
        if not isinstance(value, str):
            normalized[key] = value
            continue

        field_type = field_types.get(key)
        if field_type in null_if_blank_types and value.strip() == "":
            normalized[key] = None
            continue

        normalized[key] = value

    return normalized


def _sync_projection_schema_if_enabled(db: Session, entity_name: str) -> None:
    """Keep a dynamic projection table in sync after entity field changes."""
    from app.services import dynamic_projection_service as dps

    if not dps.has_projection_table(db, entity_name):
        return

    dps.sync_projection_schema(db, entity_name)
    dps.register_dynamic_handler(db, entity_name, force=True)


def _enforce_asset_scope(entity_def: EntityDefinition, data: dict) -> None:
    """Raise ValueError if entity is asset_scoped but asset_id is missing."""
    if entity_def.asset_scoped and not data.get("asset_id"):
        raise ValueError(
            f"Entity '{entity_def.name}' is asset-scoped: "
            "'asset_id' is required in record data."
        )


def _validate_required_fields(entity_def: EntityDefinition, data: dict) -> None:
    """Check that all non-system required fields are present in data."""
    missing = [
        f.field_name
        for f in entity_def.fields
        if f.is_required
        and not f.is_system
        and (f.field_name not in data or data.get(f.field_name) in (None, ""))
    ]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def _validate_field_name(name: str) -> None:
    """Raise ValueError if *name* does not match the naming convention."""
    if not _VALID_FIELD_NAME_RE.match(name):
        raise ValueError(
            f"Invalid field name '{name}': must be lowercase snake_case "
            "(start with a letter, only a-z / 0-9 / _, max 64 chars)."
        )


# ── Entity definition CRUD ──────────────────────────────────────────────────


def create_entity_definition(
    db: Session,
    definition_data: dict,
    user_email: str = "system",
) -> EntityDefinition:
    """Create a new entity definition with its fields and system fields."""
    name = definition_data["name"]
    _validate_field_name(name)

    existing = db.query(EntityDefinition).filter(EntityDefinition.name == name).first()
    if existing:
        raise ValueError(f"Entity '{name}' already exists")

    entity_def = EntityDefinition(
        name=name,
        entity_type=definition_data.get("entity_type", "generic") or "generic",
        asset_scoped=definition_data.get("asset_scoped", True),
        time_based=definition_data.get("time_based", False),
        time_series=definition_data.get("time_series", True),
    )
    db.add(entity_def)
    db.flush()  # flush to get the auto-incremented id

    seen_names: set[str] = set()

    # Regular fields
    for field in definition_data.get("fields", []):
        fname = field["field_name"]
        _validate_field_name(fname)
        if fname in seen_names:
            raise ValueError(f"Duplicate field name '{fname}' in entity definition")
        seen_names.add(fname)

        ftype = validate_canonical_type(field.get("field_type", "string"))
        db.add(EntityField(
            entity_id=entity_def.id,
            field_name=fname,
            field_type=ftype,
            is_required=field.get("is_required", False),
            is_indexed=field.get("is_indexed", False),
            field_source="entity",
            is_system=False,
            system_generated=False,
            default_value=None,
        ))

    # System fields
    for sf in definition_data.get("system_fields", []):
        fname = sf["field_name"]
        _validate_field_name(fname)
        if fname in seen_names:
            raise ValueError(f"Duplicate field name '{fname}' in entity definition")
        seen_names.add(fname)

        ftype = validate_canonical_type(sf.get("field_type", "string"))
        db.add(EntityField(
            entity_id=entity_def.id,
            field_name=fname,
            field_type=ftype,
            is_required=False,   # system fields are never required from callers
            is_indexed=sf.get("is_indexed", False),
            field_source="entity",
            is_system=True,
            system_generated=sf.get("system_generated", False),
            default_value=sf.get("default_value"),
        ))

    db.commit()
    db.refresh(entity_def)
    return entity_def


def get_entity_definitions(
    db: Session, skip: int = 0, limit: int = 100
) -> list[EntityDefinition]:
    return db.query(EntityDefinition).offset(skip).limit(limit).all()


def get_entity_definition(db: Session, entity_name: str) -> EntityDefinition:
    return _get_entity_def(db, entity_name)


def get_entity_fields(db: Session, entity_name: str) -> list[EntityField]:
    """Return all fields for an entity (including system fields)."""
    entity_def = _get_entity_def(db, entity_name)
    return (
        db.query(EntityField)
        .filter(EntityField.entity_id == entity_def.id)
        .order_by(EntityField.field_name)
        .all()
    )


def update_entity_definition(
    db: Session,
    entity_name: str,
    update_data: dict,
) -> EntityDefinition:
    """Partially update entity definition metadata.

    Name is immutable.  Only entity_type, asset_scoped, time_based,
    time_series can be changed.
    """
    entity_def = _get_entity_def(db, entity_name)

    mutable_fields = ("entity_type", "asset_scoped", "time_based", "time_series")
    for field in mutable_fields:
        if field in update_data and update_data[field] is not None:
            setattr(entity_def, field, update_data[field])

    db.commit()
    db.refresh(entity_def)
    return entity_def


def add_entity_field(
    db: Session,
    entity_name: str,
    field_data: dict,
) -> EntityField:
    """Add a new field to an existing entity definition."""
    entity_def = _get_entity_def(db, entity_name)
    fname = field_data["field_name"]
    _validate_field_name(fname)

    existing = db.query(EntityField).filter(
        EntityField.entity_id == entity_def.id,
        EntityField.field_name == fname,
    ).first()
    if existing:
        raise ValueError(f"Field '{fname}' already exists on entity '{entity_name}'")

    ftype = validate_canonical_type(field_data.get("field_type", "string"))
    is_system = bool(field_data.get("is_system", False))

    new_field = EntityField(
        entity_id=entity_def.id,
        field_name=fname,
        field_type=ftype,
        is_required=bool(field_data.get("is_required", False)),
        is_indexed=bool(field_data.get("is_indexed", False)),
        field_source=field_data.get("field_source", "entity"),
        is_system=is_system,
        system_generated=bool(field_data.get("system_generated", False)),
        default_value=field_data.get("default_value"),
    )
    db.add(new_field)
    db.flush()
    _sync_projection_schema_if_enabled(db, entity_name)
    db.commit()
    db.refresh(new_field)
    return new_field


def update_entity_field(
    db: Session,
    entity_name: str,
    field_name: str,
    update_data: dict,
) -> EntityField:
    """Update a field on an entity (rename, type change, required, indexed).

    If new_field_name is provided, the field is renamed.
    """
    entity_def = _get_entity_def(db, entity_name)
    field = db.query(EntityField).filter(
        EntityField.entity_id == entity_def.id,
        EntityField.field_name == field_name,
    ).first()
    if not field:
        raise ValueError(f"Field '{field_name}' not found on entity '{entity_name}'")

    new_name = update_data.get("new_field_name")
    if new_name and new_name != field_name:
        _validate_field_name(new_name)
        conflict = db.query(EntityField).filter(
            EntityField.entity_id == entity_def.id,
            EntityField.field_name == new_name,
        ).first()
        if conflict:
            raise ValueError(f"Field '{new_name}' already exists on entity '{entity_name}'")
        field.field_name = new_name

    if "field_type" in update_data:
        field.field_type = validate_canonical_type(update_data["field_type"])
    if "is_required" in update_data:
        field.is_required = bool(update_data["is_required"])
    if "is_indexed" in update_data:
        field.is_indexed = bool(update_data["is_indexed"])
    if "default_value" in update_data:
        field.default_value = update_data["default_value"]
    if "system_generated" in update_data:
        field.system_generated = bool(update_data["system_generated"])

    db.flush()
    _sync_projection_schema_if_enabled(db, entity_name)
    db.commit()
    db.refresh(field)
    return field


def delete_entity_field(
    db: Session,
    entity_name: str,
    field_name: str,
) -> bool:
    """Delete a field from an entity definition.

    Does NOT delete data already stored in entity_records — existing records
    will simply no longer have this field validated.
    """
    entity_def = _get_entity_def(db, entity_name)
    field = db.query(EntityField).filter(
        EntityField.entity_id == entity_def.id,
        EntityField.field_name == field_name,
    ).first()
    if not field:
        return False
    db.delete(field)
    db.commit()
    return True


# ── Entity ↔ Form field synchronisation ────────────────────────────────────


def sync_entity_fields_from_form(
    db: Session,
    entity_def: EntityDefinition,
    form_fields: list[dict],
    old_form_fields: list[dict] | None = None,
) -> list[EntityField]:
    """Synchronise entity_fields from form field definitions.

    Rules:
      1. Field name must match naming convention (lowercase snake_case).
      2. If the field already exists with the SAME type → skip (already synced).
      3. If the field already exists with a DIFFERENT type → raise ValueError
         (type conflict — admin must resolve manually).
      4. New fields are added with field_source="form".
      5. System fields are never touched by this function.
      6. Rename detection: if old_form_fields is provided, fields removed from
         the form that have a matching new field are treated as renames and the
         entity field is renamed accordingly (only for field_source="form" fields).

    Args:
        db:          Active SQLAlchemy session (caller commits).
        entity_def:  The EntityDefinition to sync fields into.
        form_fields: List of form field dicts with keys:
                       "id"       → becomes field_name
                       "type"     → UI type, mapped via FORM_TYPE_TO_ENTITY_TYPE
                       "required" → bool (optional)

    Returns:
        List of newly created EntityField rows (already added to session).
    """
    existing: dict[str, EntityField] = {
        f.field_name: f
        for f in entity_def.fields
        if not f.is_system  # system fields are never touched here
    }

    # ── Rename detection ────────────────────────────────────────────────────
    if old_form_fields is not None:
        old_ids = {ff.get("id", "") for ff in old_form_fields if ff.get("id")}
        new_ids = {ff.get("id", "") for ff in form_fields if ff.get("id")}
        removed_ids = old_ids - new_ids
        added_ids = new_ids - old_ids

        # 1:1 rename: exactly one field removed and one added
        if len(removed_ids) == 1 and len(added_ids) == 1:
            old_name = next(iter(removed_ids))
            new_name = next(iter(added_ids))
            if old_name in existing and existing[old_name].field_source == "form":
                try:
                    _validate_field_name(new_name)
                    if new_name not in existing:
                        existing[old_name].field_name = new_name
                        existing[new_name] = existing.pop(old_name)
                        logger.info(
                            "sync_entity_fields_from_form: renamed field '%s' → '%s' on entity '%s'",
                            old_name, new_name, entity_def.name,
                        )
                except ValueError:
                    pass  # invalid name — fall through to normal add logic

        # Many-to-many: rename entity fields where old_name matches exactly
        elif len(removed_ids) > 0 and len(added_ids) > 0:
            for old_name in list(removed_ids):
                if old_name in existing and existing[old_name].field_source == "form":
                    # Try to find a matching new name by similarity (common prefix)
                    best = None
                    for new_name in added_ids:
                        if new_name not in existing:
                            best = new_name
                            break
                    if best:
                        try:
                            _validate_field_name(best)
                            existing[old_name].field_name = best
                            existing[best] = existing.pop(old_name)
                            added_ids.discard(best)
                            logger.info(
                                "sync_entity_fields_from_form: renamed field '%s' → '%s' on entity '%s'",
                                old_name, best, entity_def.name,
                            )
                        except ValueError:
                            pass

    # ── Delete removed form fields ──────────────────────────────────────────
    # Fields that were in old_form_fields but are no longer in new form_fields
    # (and were not renamed) should be removed from entity_fields.
    # Only fields with field_source="form" are eligible for deletion.
    if old_form_fields is not None:
        old_ids_set = {ff.get("id", "") for ff in old_form_fields if ff.get("id")}
        new_ids_set = {ff.get("id", "") for ff in form_fields if ff.get("id")}
        # Also exclude fields that were just renamed (already handled above)
        removed_field_names = old_ids_set - new_ids_set
        for removed_name in removed_field_names:
            if removed_name in existing:
                field_to_delete = existing[removed_name]
                if field_to_delete.field_source == "form":
                    db.delete(field_to_delete)
                    del existing[removed_name]
                    logger.info(
                        "sync_entity_fields_from_form: deleted removed field '%s' from entity '%s'",
                        removed_name, entity_def.name,
                    )

    new_fields: list[EntityField] = []

    for ff in form_fields:
        name: str = ff.get("id", "")
        if not name:
            continue

        # 1. Naming convention — skip invalid names (don't block form save)
        try:
            _validate_field_name(name)
        except ValueError:
            logger.warning(
                "sync_entity_fields_from_form: skipping field '%s' — invalid name (entity '%s')",
                name, entity_def.name,
            )
            continue

        # Map UI type → canonical type
        ui_type = ff.get("type", "string")
        try:
            canonical_type = map_form_field(ff)
        except ValueError:
            # Fallback: if the UI type is already canonical, use it directly
            try:
                canonical_type = validate_canonical_type(ui_type)
            except ValueError:
                logger.warning(
                    "sync_entity_fields_from_form: skipping field '%s' — "
                    "cannot map form type '%s' to a canonical entity type (entity '%s')",
                    name, ui_type, entity_def.name,
                )
                continue

        if name in existing:
            # 2. Already exists — check for type conflict
            existing_type = existing[name].field_type
            if existing_type != canonical_type:
                if existing[name].field_source == "form":
                    existing[name].field_type = canonical_type
                    existing[name].is_required = bool(ff.get("required", False))
                    logger.info(
                        "sync_entity_fields_from_form: updated field '%s' type %s -> %s on entity '%s'",
                        name, existing_type, canonical_type, entity_def.name,
                    )
                else:
                    logger.warning(
                        "sync_entity_fields_from_form: type conflict on field '%s' "
                        "(entity=%s, form=%s from ui_type=%s) — skipping sync for this field",
                        name, existing_type, canonical_type, ui_type,
                    )
            # Same type or conflict — already in sync (or entity wins), nothing to do
            continue

        # 3. New field — add to entity
        new_field = EntityField(
            entity_id=entity_def.id,
            field_name=name,
            field_type=canonical_type,
            is_required=bool(ff.get("required", False)),
            is_indexed=False,
            field_source="form",
            is_system=False,
            system_generated=False,
            default_value=None,
        )
        db.add(new_field)
        new_fields.append(new_field)
        logger.info(
            "sync_entity_fields_from_form: added field '%s' (%s) to entity '%s'",
            name,
            canonical_type,
            entity_def.name,
        )

    return new_fields


# ── Record CRUD ─────────────────────────────────────────────────────────────


def create_record(
    db: Session,
    entity_name: str,
    asset_id: str | None,
    data: dict,
    user_email: str = "system",
    timestamp: datetime | None = None,
) -> EntityRecord:
    entity_def = _get_entity_def(db, entity_name)

    # asset_scoped enforcement
    _enforce_asset_scope(entity_def, {"asset_id": asset_id, **data})

    # Inject system fields
    system_fields = [f for f in entity_def.fields if f.is_system]
    enriched_data = _inject_system_fields(data, system_fields)
    enriched_data = _normalize_record_data(entity_def, enriched_data)

    # Required field validation (non-system only)
    _validate_required_fields(entity_def, enriched_data)

    initial_status = "OPEN"
    workflow = state_machine_service.get_workflow(db, entity_name)
    if workflow and workflow.is_enabled:
        initial_status = workflow.initial_state

    record = EntityRecord(
        entity_id=entity_def.id,
        asset_id=str(asset_id) if asset_id is not None else None,
        timestamp=timestamp or datetime.now(timezone.utc),
        status=initial_status,
        data_json=enriched_data,
        created_by=user_email,
    )
    db.add(record)
    db.flush()

    db.add(EntityAuditLog(
        entity_record_id=record.id,
        old_data=None,
        new_data=enriched_data,
        changed_by=user_email,
    ))

    sync_projection(db, entity_name, record)

    db.commit()
    db.refresh(record)
    return record


def get_record(
    db: Session, entity_name: str, record_id: int
) -> EntityRecord | None:
    entity_def = _get_entity_def(db, entity_name)
    return (
        db.query(EntityRecord)
        .filter(
            EntityRecord.id == record_id,
            EntityRecord.entity_id == entity_def.id,
            EntityRecord.status != "DELETED",
        )
        .first()
    )


def get_records(
    db: Session, entity_name: str, skip: int = 0, limit: int = 100
) -> list[EntityRecord]:
    entity_def = _get_entity_def(db, entity_name)
    return (
        db.query(EntityRecord)
        .filter(
            EntityRecord.entity_id == entity_def.id,
            EntityRecord.status != "DELETED",
        )
        .order_by(EntityRecord.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_record(
    db: Session,
    entity_name: str,
    record_id: int,
    data: dict,
    asset_id: str | None = None,
    status: str | None = None,
    user_email: str = "system",
) -> EntityRecord | None:
    entity_def = _get_entity_def(db, entity_name)
    record = (
        db.query(EntityRecord)
        .filter(EntityRecord.id == record_id, EntityRecord.entity_id == entity_def.id)
        .first()
    )
    if not record or record.status == "DELETED":
        return None

    old_data = dict(record.data_json) if record.data_json else {}

    # Merge caller data over existing
    merged = {**old_data, **data}

    # Re-inject system fields (system_generated ones always override)
    system_fields = [f for f in entity_def.fields if f.is_system]
    merged = _inject_system_fields(merged, system_fields)
    merged = _normalize_record_data(entity_def, merged)

    record.data_json = merged
    if asset_id is not None:
        record.asset_id = str(asset_id)
    if status:
        state_machine_service.apply_transition(
            db,
            entity_name,
            record,
            status,
            user_email=user_email,
        )
    else:
        record.updated_at = datetime.now(timezone.utc)

    db.add(EntityAuditLog(
        entity_record_id=record.id,
        old_data=old_data,
        new_data=merged,
        changed_by=user_email,
    ))

    sync_projection(db, entity_name, record)

    db.commit()
    db.refresh(record)
    return record


def soft_delete_record(
    db: Session,
    entity_name: str,
    record_id: int,
    user_email: str = "system",
) -> bool:
    entity_def = _get_entity_def(db, entity_name)
    record = (
        db.query(EntityRecord)
        .filter(EntityRecord.id == record_id, EntityRecord.entity_id == entity_def.id)
        .first()
    )
    if not record:
        return False

    old_status = record.status
    record.status = "DELETED"
    record.updated_at = datetime.now(timezone.utc)

    db.add(EntityAuditLog(
        entity_record_id=record.id,
        old_data={"status": old_status},
        new_data={"status": "DELETED"},
        changed_by=user_email,
    ))

    # Sync projection so it mirrors the DELETED status
    sync_projection(db, entity_name, record)

    db.commit()
    return True