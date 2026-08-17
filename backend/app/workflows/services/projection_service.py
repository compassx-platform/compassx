"""Projection sync service.

Dispatches entity record changes to the appropriate projection handler
via the PROJECTION_REGISTRY.  This module contains NO entity-specific
logic — all handler code lives in app/projections/<entity_name>.py.

To add a new projection:
  1. Create app/projections/<entity_name>.py (implements ProjectionHandler)
  2. Import it in app/main.py to trigger self-registration
  3. Done — no changes needed here.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.entity import EntityRecord
from app.services.projection_registry import get_handler

logger = logging.getLogger(__name__)


def sync_projection(db: Session, entity_name: str, record: EntityRecord) -> None:
    """Dispatch a projection sync for the given entity record.

    Looks up the registered handler for *entity_name* and calls its
    ``sync`` method.  If no handler is registered, the call is a no-op
    (not an error — entities without projections are valid).

    Lazy registration
    -----------------
    If no handler is found in the registry but a flat projection table
    exists for this entity, the handler is auto-registered on-the-fly.
    This handles two real-world scenarios:

      1. Server restart — ``auto_register_projections`` ran at startup
         but failed silently (DB not yet ready, exception swallowed in
         main.py's try/except).
      2. Projection enabled in a different worker/process — the registry
         is in-process memory; another pod may have registered the handler
         but this pod's registry is empty.

    Error isolation
    ---------------
    Projection sync failures are logged but do NOT propagate.  A broken
    projection must never prevent a record from being saved — the flat
    table can always be rebuilt via ``backfill_projection``.

    Args:
        db:          Active SQLAlchemy session (caller owns commit).
        entity_name: The entity_definitions.name value.
        record:      The EntityRecord that was just mutated.
    """
    handler = get_handler(entity_name)

    # ── Lazy registration ────────────────────────────────────────────────────
    if handler is None:
        try:
            from app.services import dynamic_projection_service as dps  # avoid circular at module level
            if dps.has_projection_table(db, entity_name):
                logger.info(
                    "projection_service: lazy-registering handler for entity '%s' "
                    "(flat table exists but handler was not in registry)",
                    entity_name,
                )
                dps.register_dynamic_handler(db, entity_name)
                handler = get_handler(entity_name)
        except Exception as _reg_exc:
            logger.warning(
                "projection_service: lazy registration failed for entity '%s': %s",
                entity_name, _reg_exc,
            )

    if handler is None:
        logger.debug(
            "projection_service: no handler registered for entity '%s' — skipping",
            entity_name,
        )
        return

    # ── Sync ─────────────────────────────────────────────────────────────────
    logger.debug(
        "projection_service: syncing projection for entity '%s', record %s",
        entity_name,
        record.id,
    )
    try:
        handler.sync(db, record)
    except Exception as exc:
        # Projection failures must never block record persistence.
        # Log the error so operators can investigate and backfill later.
        logger.error(
            "projection_service: sync failed for entity '%s', record %s — "
            "record will be saved but projection table may be stale. "
            "Run backfill_projection to repair. Error: %s",
            entity_name,
            record.id,
            exc,
            exc_info=True,
        )
