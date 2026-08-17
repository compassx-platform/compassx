"""Time-series data editor routes.

Endpoints:
  GET  /api/v1/timeseries                          – query with filters + pagination
  GET  /api/v1/timeseries/tags                     – list tag definitions
  POST /api/v1/timeseries/tags/seed                – seed tags from raw_data
  POST /api/v1/timeseries/batch-update             – inline batch edit
  POST /api/v1/timeseries/upload                   – upload CSV/Excel → staging
  POST /api/v1/timeseries/upload/{batch_id}/validate
  GET  /api/v1/timeseries/upload/{batch_id}/diff
  POST /api/v1/timeseries/upload/{batch_id}/apply
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, get_raw_db
from app.dependencies import get_current_user
from app.schemas.timeseries import (
    ApplyResponse,
    BatchUpdateRequest,
    BatchUpdateResponse,
    DiffResponse,
    TagDefinitionOut,
    TimeseriesQueryResponse,
    UploadInitResponse,
    ValidateResponse,
)
from app.services import timeseries_service, upload_service
from app.services.enrichment_service import enrich_asset_names

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/timeseries", tags=["Time-Series"])


# ---------------------------------------------------------------------------
# Debug / probe endpoint – verify raw_data table is reachable
# ---------------------------------------------------------------------------

@router.get("/debug/probe")
def probe_raw_data(
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Comprehensive DB diagnostic:
    - Current database name
    - All schemas in current DB
    - All tables named 'raw_data' across all schemas (with row counts)
    - All tables in public schema
    - Sample rows from public.raw_data if it exists
    """
    try:
        result: dict = {}

        # 1. Current database
        current_db = db.execute(text("SELECT current_database()")).scalar()
        result["current_database"] = current_db
        log.info("PROBE: current_database = %s", current_db)

        # 2. All schemas
        schemas = db.execute(
            text("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
        ).fetchall()
        result["schemas"] = [r[0] for r in schemas]
        log.info("PROBE: schemas = %s", result["schemas"])

        # 3. Find ALL tables named 'raw_data' in any schema
        raw_data_tables = db.execute(
            text(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_name = 'raw_data'
                ORDER BY table_schema
                """
            )
        ).fetchall()
        result["raw_data_locations"] = [
            {"schema": r[0], "table": r[1]} for r in raw_data_tables
        ]
        log.info("PROBE: raw_data found in schemas: %s", result["raw_data_locations"])

        # 4. Row count for each raw_data location found
        row_counts = []
        for loc in result["raw_data_locations"]:
            try:
                cnt = db.execute(
                    text(f"SELECT COUNT(*) FROM {loc['schema']}.raw_data")
                ).scalar()
                row_counts.append({"schema": loc["schema"], "count": cnt})
                log.info("PROBE: %s.raw_data has %d rows", loc["schema"], cnt)
            except Exception as e:
                row_counts.append({"schema": loc["schema"], "count": f"error: {e}"})
        result["raw_data_row_counts"] = row_counts

        # 5. All tables in public schema
        public_tables = db.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
        ).fetchall()
        result["public_tables"] = [r[0] for r in public_tables]
        log.info("PROBE: public tables = %s", result["public_tables"])

        # 6. Sample from public.raw_data if it exists and has rows
        sample = []
        for rc in row_counts:
            if rc.get("count", 0) and isinstance(rc["count"], int) and rc["count"] > 0:
                try:
                    rows = db.execute(
                        text(
                            f"SELECT ts, asset_id, tag_def_id, tag_def_name, value "
                            f"FROM {rc['schema']}.raw_data ORDER BY ts ASC LIMIT 3"
                        )
                    ).fetchall()
                    sample = [
                        {
                            "schema": rc["schema"],
                            "ts": str(r[0]),
                            "asset_id": r[1],
                            "tag_def_id": r[2],
                            "tag_def_name": r[3],
                            "value": r[4],
                        }
                        for r in rows
                    ]
                    log.info("PROBE: sample rows from %s.raw_data: %s", rc["schema"], sample)
                except Exception as e:
                    log.warning("PROBE: could not sample %s.raw_data: %s", rc["schema"], e)
        result["sample_rows"] = sample

        return result

    except Exception as exc:
        log.error("probe error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

@router.get("", response_model=TimeseriesQueryResponse)
async def query_timeseries(
    asset_ids: Annotated[list[int] | None, Query(alias="asset_ids[]")] = None,
    tag_def_ids: Annotated[list[int] | None, Query(alias="tag_def_ids[]")] = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    size: int = 100,
    authkey: str = Header(...),
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Query time-series data with optional asset/tag/time filters.

    Returns enriched rows (asset_name, tag_name resolved).
    """
    if page < 1:
        page = 1
    if size < 1 or size > 1000:
        size = 100

    log.info(
        "GET /timeseries | asset_ids=%s tag_def_ids=%s start=%s end=%s page=%s size=%s user=%s",
        asset_ids, tag_def_ids, start_time, end_time, page, size,
        user.get("email", "unknown"),
    )

    # First do a lightweight query to get distinct asset_ids in result set
    # then enrich in batch before building the full response
    result = timeseries_service.query_timeseries(
        db=db,
        asset_ids=asset_ids,
        tag_def_ids=tag_def_ids,
        start_time=start_time,
        end_time=end_time,
        page=page,
        size=size,
        asset_name_map=None,  # will enrich below
    )

    # Batch-enrich asset names
    unique_ids = list({str(row.asset_id) for row in result.items})
    if unique_ids:
        name_map = await enrich_asset_names(unique_ids, authkey)
        log.debug("asset name_map: %s", name_map)
        for row in result.items:
            row.asset_name = name_map.get(str(row.asset_id), f"Asset {row.asset_id}")
    else:
        log.info("No rows returned – skipping asset enrichment")

    log.info(
        "GET /timeseries response | total=%d items=%d pages=%d",
        result.total, len(result.items), result.pages,
    )
    return result


# ---------------------------------------------------------------------------
# Tag definitions
# ---------------------------------------------------------------------------

@router.get("/tags", response_model=list[TagDefinitionOut])
def list_tags(
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """List all known tag definitions."""
    return timeseries_service.list_tag_definitions(db)


@router.post("/tags/seed", status_code=200)
def seed_tags(
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Seed tag_definitions table from existing raw_data.tag_def_name values.

    Safe to call multiple times (idempotent).
    """
    inserted = timeseries_service.seed_tag_definitions(db)
    return {"seeded": inserted}


# ---------------------------------------------------------------------------
# Inline batch update
# ---------------------------------------------------------------------------

@router.post("/batch-update", response_model=BatchUpdateResponse)
def batch_update(
    body: BatchUpdateRequest,
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Batch-update (UPSERT) time-series values from inline table edits.

    Writes an edit log entry for every changed row.
    """
    try:
        return timeseries_service.batch_update(
            db=db,
            rows=body.rows,
            user_email=user.get("email", "system"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Upload flow
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadInitResponse, status_code=201)
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Step 1: Upload a CSV or Excel file.

    Parses the file and stores all rows in upload_staging with status='pending'.
    Returns a batch_id to use in subsequent steps.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    log.info("upload_file: filename=%s size=%d bytes", file.filename, len(file_bytes))
    try:
        result = upload_service.create_batch(db=db, file_bytes=file_bytes, filename=file.filename)
        log.info("upload_file: batch_id=%s row_count=%d", result.batch_id, result.row_count)
        return result
    except Exception as exc:
        log.error("upload_file error: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{batch_id}/validate", response_model=ValidateResponse)
async def validate_batch(
    batch_id: uuid.UUID,
    authkey: str = Header(...),
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Step 2: Validate all rows in a batch.

    Resolves asset/tag references, checks values, detects duplicates.
    Updates status of each staging row (valid / updated / duplicate / invalid).
    """
    try:
        return await upload_service.validate_batch(
            db=db,
            batch_id=batch_id,
            authkey=authkey,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/upload/{batch_id}/diff", response_model=DiffResponse)
def get_diff(
    batch_id: uuid.UUID,
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Step 3: Get diff preview for a validated batch.

    Returns rows grouped into: new / updated / duplicate / invalid tabs.
    """
    return upload_service.get_diff(db=db, batch_id=batch_id)


@router.post("/upload/{batch_id}/apply", response_model=ApplyResponse)
def apply_batch(
    batch_id: uuid.UUID,
    db: Session = Depends(get_raw_db),
    user: dict = Depends(get_current_user),
):
    """Step 4: Apply a validated batch to raw_data.

    UPSERTs all valid/updated rows, writes edit log, marks staging rows as done.
    Skips invalid and duplicate rows.
    """
    try:
        return upload_service.apply_batch(
            db=db,
            batch_id=batch_id,
            user_email=user.get("email", "system"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
