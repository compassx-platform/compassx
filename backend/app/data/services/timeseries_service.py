"""Time-series query and inline batch-update service.

Responsibilities:
  - query_timeseries  : paginated read from raw_data + asset enrichment
  - batch_update      : validate → fetch old values → UPSERT → write edit log
  - list_tag_defs     : return all known tag definitions
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.timeseries import RawData, TagDefinition, TimeseriesEditLog
from app.schemas.timeseries import (
    BatchUpdateItem,
    BatchUpdateResponse,
    TagDefinitionOut,
    TimeseriesQueryResponse,
    TimeseriesRow,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query_timeseries(
    db: Session,
    asset_ids: list[int] | None,
    tag_def_ids: list[int] | None,
    start_time: datetime | None,
    end_time: datetime | None,
    page: int,
    size: int,
    # Pre-resolved asset name map passed in from the route (async enrichment)
    asset_name_map: dict[str, str] | None = None,
) -> TimeseriesQueryResponse:
    """Query raw_data with optional filters, return enriched paginated response."""

    log.info(
        "query_timeseries called | asset_ids=%s tag_def_ids=%s start=%s end=%s page=%s size=%s",
        asset_ids, tag_def_ids, start_time, end_time, page, size,
    )

    q = db.query(RawData)

    if asset_ids:
        q = q.filter(RawData.asset_id.in_(asset_ids))
    if tag_def_ids:
        q = q.filter(RawData.tag_def_id.in_(tag_def_ids))
    if start_time:
        q = q.filter(RawData.ts >= start_time)
    if end_time:
        q = q.filter(RawData.ts <= end_time)

    q = q.order_by(RawData.ts.asc(), RawData.asset_id.asc(), RawData.tag_def_id.asc())

    # Log the compiled SQL for debugging
    try:
        compiled = q.statement.compile(
            dialect=db.bind.dialect,
            compile_kwargs={"literal_binds": True},
        )
        log.debug("SQL: %s", str(compiled))
    except Exception as exc:
        log.debug("Could not compile SQL for logging: %s", exc)

    # Raw SQL sanity check – compare ORM count vs direct SQL count
    raw_count = db.execute(text("SELECT COUNT(*) FROM public.raw_data")).scalar()
    log.info("RAW SQL COUNT(public.raw_data) = %d", raw_count)

    # Also fetch first row via raw SQL for comparison
    first_row = db.execute(
        text("SELECT ts, asset_id, tag_def_id, value FROM public.raw_data LIMIT 1")
    ).fetchone()
    log.info("RAW SQL first row = %s", first_row)

    total = q.count()
    log.info("ORM q.count() = %d", total)
    pages = math.ceil(total / size) if size > 0 else 0
    rows = q.offset((page - 1) * size).limit(size).all()
    log.info("ORM rows returned: %d", len(rows))

    # Build tag name map from tag_definitions table.
    # tag_def_id may come back as Decimal from PostgreSQL numeric columns – normalise to int.
    tag_ids = list({int(r.tag_def_id) for r in rows})
    tag_map: dict[int, str] = {}
    if tag_ids:
        tags = db.query(TagDefinition).filter(TagDefinition.id.in_(tag_ids)).all()
        tag_map = {int(t.id): t.name for t in tags}
        log.debug("tag_map from tag_definitions: %s", tag_map)
        # Fallback: use tag_def_name from raw_data if tag_definitions not seeded yet
        for r in rows:
            tid = int(r.tag_def_id)
            if tid not in tag_map and r.tag_def_name:
                tag_map[tid] = r.tag_def_name
        log.debug("tag_map after raw_data fallback: %s", tag_map)

    name_map = asset_name_map or {}

    items = [
        TimeseriesRow(
            ts=r.ts,
            asset_id=int(r.asset_id),
            asset_name=name_map.get(str(int(r.asset_id)), f"Asset {r.asset_id}"),
            tag_def_id=int(r.tag_def_id),
            tag_name=tag_map.get(int(r.tag_def_id), f"Tag {r.tag_def_id}"),
            value=float(r.value) if r.value is not None else None,
        )
        for r in rows
    ]

    return TimeseriesQueryResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Batch update (inline editing)
# ---------------------------------------------------------------------------

def batch_update(
    db: Session,
    rows: list[BatchUpdateItem],
    user_email: str = "system",
) -> BatchUpdateResponse:
    """UPSERT a batch of time-series values and write an edit log entry for each.

    Returns counts of updated vs newly inserted rows.
    """
    updated_count = 0
    inserted_count = 0

    for item in rows:
        existing: RawData | None = (
            db.query(RawData)
            .filter(
                RawData.ts == item.ts,
                RawData.asset_id == item.asset_id,
                RawData.tag_def_id == item.tag_def_id,
            )
            .first()
        )

        old_value: float | None = None

        if existing:
            old_value = existing.value
            existing.value = item.value
            updated_count += 1
        else:
            new_row = RawData(
                ts=item.ts,
                asset_id=item.asset_id,
                tag_def_id=item.tag_def_id,
                value=item.value,
            )
            db.add(new_row)
            inserted_count += 1

        # Write edit log regardless of insert/update
        db.add(
            TimeseriesEditLog(
                ts=item.ts,
                asset_id=item.asset_id,
                tag_def_id=item.tag_def_id,
                old_value=old_value,
                new_value=item.value,
                updated_by=user_email,
                updated_at=datetime.now(timezone.utc),
                source="inline",
            )
        )

    db.commit()
    return BatchUpdateResponse(updated=updated_count, inserted=inserted_count)


# ---------------------------------------------------------------------------
# Tag definitions
# ---------------------------------------------------------------------------

def list_tag_definitions(db: Session) -> list[TagDefinitionOut]:
    """Return all known tag definitions."""
    tags = db.query(TagDefinition).order_by(TagDefinition.name).all()
    return [TagDefinitionOut.model_validate(t) for t in tags]


def seed_tag_definitions(db: Session) -> int:
    """Seed tag_definitions from distinct tag_def_name values in raw_data.

    Safe to call multiple times (idempotent).
    Returns number of new tags inserted.
    """
    result = db.execute(
        text(
            """
            INSERT INTO tag_definitions (name)
            SELECT DISTINCT tag_def_name
            FROM public.raw_data
            WHERE tag_def_name IS NOT NULL
              AND tag_def_name <> ''
            ON CONFLICT (name) DO NOTHING
            """
        )
    )
    db.commit()
    return result.rowcount or 0
