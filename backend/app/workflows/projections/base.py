"""Abstract base class for all projection handlers.

Contract
--------
Every concrete handler MUST:

1. Implement `entity_name` (str property) — used as the registry key.
2. Implement `sync(db, record)` — upsert the projection row.
3. Upsert by `record.id` (never create duplicates).
4. Honour `record.status`:
   - "DELETED" → mark the projection row as DELETED (do NOT hard-delete).
   - Any other status → insert or overwrite the projection row.
5. Map all relevant fields from `record.data_json` consistently.
6. NOT commit the session — the caller (entity_service) owns the transaction.

Example skeleton
----------------
    from app.projections.base import ProjectionHandler
    from app.services.projection_registry import register

    class MyEntityProjectionHandler(ProjectionHandler):
        @property
        def entity_name(self) -> str:
            return "my_entity"

        def sync(self, db: Session, record: EntityRecord) -> None:
            data = record.data_json or {}
            existing = db.query(MyEntityFlat).filter_by(record_id=record.id).first()

            if record.status == "DELETED":
                if existing:
                    existing.status = "DELETED"
                return

            fields = {
                "record_id": record.id,
                "asset_id":  record.asset_id,
                "status":    record.status,
                # ... map remaining fields from data ...
            }

            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                db.add(MyEntityFlat(**fields))

    # Self-register on import — no changes needed in core services
    register(MyEntityProjectionHandler())
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.models.entity import EntityRecord


class ProjectionHandler(ABC):
    """Abstract contract for entity projection handlers."""

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """The entity_name this handler is registered for.

        Must match the value stored in entity_definitions.name exactly.
        """
        ...

    @abstractmethod
    def sync(self, db: Session, record: EntityRecord) -> None:
        """Upsert the projection row for the given entity record.

        Args:
            db:     Active SQLAlchemy session.  Do NOT call db.commit() here —
                    the caller owns the transaction boundary.
            record: The EntityRecord that was just created, updated, or
                    soft-deleted.  Inspect record.status to determine the
                    operation type ("DELETED" = soft-delete).

        Raises:
            Any exception will bubble up to entity_service, which will
            roll back the transaction and return an error to the caller.
        """
        ...