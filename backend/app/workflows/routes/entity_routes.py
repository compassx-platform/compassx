"""Entity CRUD routes – generic for any registered entity."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.entity import (
    EntityDefinitionCreate,
    EntityDefinitionDetailResponse,
    EntityDefinitionResponse,
    EntityDefinitionUpdate,
    EntityFieldCreate,
    EntityFieldResponse,
    EntityFieldUpdate,
    EntityRecordCreate,
    EntityRecordResponse,
    EntityRecordUpdate,
)
from app.services import entity_service
from app.services import dynamic_projection_service as dps

router = APIRouter(prefix="/api/v1/entities", tags=["Entities"])


# ── Entity definition endpoints ─────────────────────────────────────────────


@router.get("", response_model=list[EntityDefinitionResponse])
def list_entity_definitions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all registered entity types."""
    return entity_service.get_entity_definitions(db, skip=skip, limit=limit)


@router.post("", response_model=EntityDefinitionDetailResponse, status_code=201)
def create_entity_definition(
    body: EntityDefinitionCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Register a new entity type with its fields and system fields."""
    try:
        return entity_service.create_entity_definition(
            db,
            definition_data=body.model_dump(),
            user_email=user.get("email", "system"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{entity_name}", response_model=EntityDefinitionDetailResponse)
def get_entity_definition(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a single entity definition with its full field list."""
    try:
        return entity_service.get_entity_definition(db, entity_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{entity_name}", response_model=EntityDefinitionDetailResponse)
def update_entity_definition(
    entity_name: str,
    body: EntityDefinitionUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update entity definition metadata (entity_type, asset_scoped, time_based).

    Entity name is immutable.
    """
    try:
        return entity_service.update_entity_definition(
            db,
            entity_name=entity_name,
            update_data=body.model_dump(exclude_none=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Field endpoints ──────────────────────────────────────────────────────────


@router.get("/{entity_name}/fields", response_model=list[EntityFieldResponse])
def get_entity_fields(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return all fields (including system fields) for an entity."""
    try:
        return entity_service.get_entity_fields(db, entity_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{entity_name}/fields", response_model=EntityFieldResponse, status_code=201)
def add_entity_field(
    entity_name: str,
    body: EntityFieldCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Add a new field to an existing entity definition."""
    try:
        return entity_service.add_entity_field(db, entity_name, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{entity_name}/fields/{field_name}", response_model=EntityFieldResponse)
def update_entity_field(
    entity_name: str,
    field_name: str,
    body: EntityFieldUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update or rename a field on an entity definition."""
    try:
        return entity_service.update_entity_field(
            db, entity_name, field_name, body.model_dump(exclude_none=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Projection endpoints ─────────────────────────────────────────────────────


@router.get("/{entity_name}/projection")
def get_projection_status(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return whether a projection table exists for this entity."""
    enabled = dps.has_projection_table(db, entity_name)
    return {
        "entity_name": entity_name,
        "enabled": enabled,
        "table": dps.flat_table_name(entity_name) if enabled else None,
    }


@router.post("/{entity_name}/projection")
def enable_projection(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create the {entity_name}_flat projection table and backfill existing records.

    Idempotent — safe to call multiple times.
    """
    try:
        result = dps.enable_projection(db, entity_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Projection creation failed: {e}")


@router.post("/{entity_name}/projection/sync-schema")
def sync_projection_schema(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Add any missing columns to the projection table (call after adding new fields)."""
    if not dps.has_projection_table(db, entity_name):
        raise HTTPException(status_code=404, detail="Projection table does not exist for this entity")
    dps.sync_projection_schema(db, entity_name)
    return {"status": "schema synced", "table": dps.flat_table_name(entity_name)}


@router.get("/{entity_name}/projection/orphaned-columns")
def get_orphaned_projection_columns(
    entity_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return columns in the flat table that are no longer in entity_fields.

    These are safe to drop once the admin confirms old data is no longer needed.
    """
    if not dps.has_projection_table(db, entity_name):
        return {"entity_name": entity_name, "orphaned_columns": []}
    orphaned = dps.get_orphaned_projection_columns(db, entity_name)
    return {"entity_name": entity_name, "orphaned_columns": orphaned}


@router.delete("/{entity_name}/projection/columns")
def drop_projection_columns(
    entity_name: str,
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Permanently drop specified orphaned columns from the flat projection table.

    Body: { "columns": ["col1", "col2"] }

    WARNING: All data stored in these columns is permanently deleted.
    Only orphaned columns (not in entity_fields) may be dropped.
    """
    columns: list[str] = body.get("columns", [])
    if not columns:
        raise HTTPException(status_code=400, detail="No columns specified")
    try:
        dropped = dps.drop_projection_columns(db, entity_name, columns)
        return {
            "entity_name": entity_name,
            "dropped": dropped,
            "message": f"Dropped {len(dropped)} column(s): {', '.join(dropped)}",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to drop projection columns for entity '%s': %s", entity_name, e)
        raise HTTPException(status_code=500, detail=f"Column drop failed: {e}")


@router.delete("/{entity_name}/fields/{field_name}")
def delete_entity_field(
    entity_name: str,
    field_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a field from an entity definition."""
    deleted = entity_service.delete_entity_field(db, entity_name, field_name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Field '{field_name}' not found")
    return {"status": "deleted"}


# ── Record endpoints ─────────────────────────────────────────────────────────


@router.post("/{entity_name}/records", response_model=EntityRecordResponse, status_code=201)
def create_entity_record(
    entity_name: str,
    body: EntityRecordCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        record = entity_service.create_record(
            db,
            entity_name=entity_name,
            asset_id=body.asset_id,
            data=body.data,
            user_email=user.get("email", "system"),
            timestamp=body.timestamp,
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create record for entity '%s': %s", entity_name, e)
        raise HTTPException(status_code=500, detail=f"Record creation failed: {e}")


@router.get("/{entity_name}/records/{record_id}", response_model=EntityRecordResponse)
def get_entity_record(
    entity_name: str,
    record_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    record = entity_service.get_record(db, entity_name, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/{entity_name}/records", response_model=list[EntityRecordResponse])
def get_entity_records(
    entity_name: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List records for a specific entity."""
    return entity_service.get_records(db, entity_name, skip=skip, limit=limit)


@router.put("/{entity_name}/records/{record_id}", response_model=EntityRecordResponse)
def update_entity_record(
    entity_name: str,
    record_id: int,
    body: EntityRecordUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        record = entity_service.update_record(
            db,
            entity_name=entity_name,
            record_id=record_id,
            asset_id=body.asset_id,
            data=body.data,
            status=body.status,
            user_email=user.get("email", "system"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception("Failed to update record %s for entity '%s': %s", record_id, entity_name, e)
        raise HTTPException(status_code=500, detail=f"Record update failed: {e}")

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.delete("/{entity_name}/records/{record_id}")
def delete_entity_record(
    entity_name: str,
    record_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    deleted = entity_service.soft_delete_record(
        db,
        entity_name=entity_name,
        record_id=record_id,
        user_email=user.get("email", "system"),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "deleted"}