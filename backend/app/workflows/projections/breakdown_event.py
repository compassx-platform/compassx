"""Projection handler for the 'breakdown_event' entity.

Upserts rows in breakdown_events_flat from entity_records.data_json.

Handles:
  - INSERT  (new record)
  - UPDATE  (existing record)
  - SOFT DELETE  (record.status == "DELETED")

Self-registers on import.  To activate, add this import to app/main.py:
    import app.projections.breakdown_event  # noqa: F401
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.entity import EntityRecord
from app.models.projection import BreakdownEventFlat
from app.projections.base import ProjectionHandler
from app.services.projection_registry import register

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field mapping
# Maps data_json keys → BreakdownEventFlat column names
# Add new mappings here as the entity schema evolves — no other files change.
# ---------------------------------------------------------------------------
_FIELD_MAP: dict[str, str] = {
    "child_asset_id":  "child_asset_id",
    "breakdown_type":  "breakdown_type",
    "severity":        "severity",
    "description":     "description",
}


class BreakdownEventProjectionHandler(ProjectionHandler):
    """Projection handler for breakdown_event entity."""

    @property
    def entity_name(self) -> str:
        return "breakdown_event"

    def sync(self, db: Session, record: EntityRecord) -> None:
        """Upsert breakdown_events_flat from the given entity record.

        Contract (from ProjectionHandler):
          - Upsert by record.id
          - Handle status = "DELETED" by marking projection row as DELETED
          - Do NOT commit — caller owns the transaction
        """
        existing: BreakdownEventFlat | None = (
            db.query(BreakdownEventFlat)
            .filter(BreakdownEventFlat.record_id == record.id)
            .first()
        )

        # ── Soft delete ──────────────────────────────────────────────────────
        if record.status == "DELETED":
            if existing:
                existing.status = "DELETED"
                logger.debug("breakdown_event projection: marked record %s as DELETED", record.id)
            return

        # ── Build field values ───────────────────────────────────────────────
        data = record.data_json or {}

        mapped_fields: dict = {
            "record_id":   record.id,
            "asset_id":    record.asset_id,
            "timestamp":   record.timestamp,
            "status":      record.status,
            "created_by":  record.created_by,
        }

        # Apply _FIELD_MAP — coerce to str for nullable string columns
        for src_key, dest_col in _FIELD_MAP.items():
            raw = data.get(src_key)
            mapped_fields[dest_col] = str(raw) if raw is not None else None

        # ── Upsert ──────────────────────────────────────────────────────────
        if existing:
            for col, val in mapped_fields.items():
                setattr(existing, col, val)
            logger.debug("breakdown_event projection: updated record %s", record.id)
        else:
            db.add(BreakdownEventFlat(**mapped_fields))
            logger.debug("breakdown_event projection: inserted record %s", record.id)


# Self-register — triggered on first import of this module
register(BreakdownEventProjectionHandler())