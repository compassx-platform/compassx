"""Upload pipeline service: parse → validate → diff → apply.

Flow:
  1. create_batch   – parse CSV/Excel, insert rows into upload_staging
  2. validate_batch – resolve asset/tag refs, detect duplicates, mark status
  3. get_diff       – return rows grouped by status
  4. apply_batch    – UPSERT valid rows into raw_data, write edit log, mark done
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.timeseries import RawData, TagDefinition, TimeseriesEditLog, UploadStaging
from app.schemas.timeseries import (
    ApplyResponse,
    DiffResponse,
    StagingRowOut,
    UploadInitResponse,
    ValidateResponse,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BATCH_DONE_STATUS = "done"


def _normalise_ref(raw: Any) -> str | None:
    """Convert a raw cell value to a clean string reference.

    Handles pandas float-formatted integers (1.0 → '1'), NaN, and None.
    """
    if raw is None:
        return None
    import math
    try:
        if isinstance(raw, float):
            if math.isnan(raw):
                return None
            # Convert 1.0 → '1', 1.5 → '1.5'
            return str(int(raw)) if raw == int(raw) else str(raw)
        return str(raw).strip() or None
    except (ValueError, TypeError):
        return str(raw).strip() or None


def _parse_file(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Parse CSV or Excel file into a list of raw row dicts.

    Expected columns (case-insensitive, flexible names):
      ts / timestamp / date / datetime
      asset / asset_ref / asset_name / asset_id
      tag / tag_ref / tag_name / metric
      value / val
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "pandas is required for file parsing. Install it with: pip install pandas openpyxl"
        ) from exc

    lower_name = filename.lower()
    if lower_name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif lower_name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError(f"Unsupported file type: {filename}. Use CSV or Excel.")

    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]

    col_map = {
        "ts": ["ts", "timestamp", "date", "datetime", "time"],
        "asset_ref": ["asset", "asset_ref", "asset_name", "asset_id"],
        "tag_ref": ["tag", "tag_ref", "tag_name", "tag_def_id", "tag_id", "metric", "tag_def_name"],
        "value": ["value", "val"],
    }

    resolved: dict[str, str] = {}
    for target, candidates in col_map.items():
        for c in candidates:
            if c in df.columns:
                resolved[target] = c
                break

    rows = []
    for i, row in enumerate(df.itertuples(index=False), start=1):
        raw: dict[str, Any] = {"_row_number": i}
        for target, src_col in resolved.items():
            raw[target] = getattr(row, src_col, None)
        rows.append(raw)

    return rows


def _parse_ts(raw: Any) -> datetime | None:
    """Try to parse a timestamp value from various formats."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        import pandas as pd
        parsed = pd.to_datetime(raw, utc=True)
        return parsed.to_pydatetime()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Step 1: Create batch
# ---------------------------------------------------------------------------

def create_batch(
    db: Session,
    file_bytes: bytes,
    filename: str,
) -> UploadInitResponse:
    """Parse file and insert all rows into upload_staging with status='pending'."""

    raw_rows = _parse_file(file_bytes, filename)
    batch_id = uuid.uuid4()

    staging_rows = []
    for raw in raw_rows:
        ts_val = _parse_ts(raw.get("ts"))
        staging_rows.append(
            UploadStaging(
                batch_id=batch_id,
                row_number=raw["_row_number"],
                ts=ts_val,
                asset_ref=_normalise_ref(raw.get("asset_ref")),
                tag_ref=_normalise_ref(raw.get("tag_ref")),
                value=float(raw["value"]) if raw.get("value") is not None else None,
                status="pending",
            )
        )

    db.bulk_save_objects(staging_rows)
    db.commit()

    return UploadInitResponse(batch_id=str(batch_id), row_count=len(staging_rows))


# ---------------------------------------------------------------------------
# Step 2: Validate batch
# ---------------------------------------------------------------------------

async def validate_batch(
    db: Session,
    batch_id: uuid.UUID,
    authkey: str,
) -> ValidateResponse:
    """Validate all pending staging rows for a batch.

    For each row:
      - Check timestamp is present and parseable
      - Resolve asset_ref → asset_id via asset manager proxy
      - Resolve tag_ref → tag_def_id via tag_definitions table
      - Check value is numeric and non-null
      - Detect duplicates against raw_data (mark as 'duplicate' if exists, 'valid' if new/updated)
    """
    from app.config import settings
    import httpx

    rows: list[UploadStaging] = (
        db.query(UploadStaging)
        .filter(
            UploadStaging.batch_id == batch_id,
            UploadStaging.status == "pending",
        )
        .all()
    )

    if not rows:
        # Re-count from existing statuses
        return _build_validate_response(db, batch_id)

    # ------------------------------------------------------------------
    # Build tag name → id map from tag_definitions
    # ------------------------------------------------------------------
    all_tags = db.query(TagDefinition).all()
    tag_name_to_id: dict[str, int] = {t.name.lower(): t.id for t in all_tags}

    # ------------------------------------------------------------------
    # Collect unique asset refs to resolve in batch
    # ------------------------------------------------------------------
    unique_asset_refs = list({r.asset_ref for r in rows if r.asset_ref})
    asset_ref_to_id: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=15) as client:
        for ref in unique_asset_refs:
            # Try numeric ID first
            if ref.isdigit():
                asset_ref_to_id[ref] = int(ref)
                continue
            # Try name lookup via asset manager
            try:
                resp = await client.get(
                    f"{settings.ASSET_MANAGER_BASE_URL}/asset-manager/api/v1/assets",
                    params={"name": ref},
                    headers={"authkey": authkey},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    items = body.get("items", body if isinstance(body, list) else [])
                    if items:
                        asset_ref_to_id[ref] = int(items[0].get("id", 0))
            except httpx.RequestError:
                pass  # Will be marked invalid below

    # ------------------------------------------------------------------
    # Validate each row
    # ------------------------------------------------------------------
    for row in rows:
        errors: list[str] = []

        # Timestamp
        if row.ts is None:
            errors.append("Missing or invalid timestamp")

        # Asset
        resolved_asset_id: int | None = None
        if not row.asset_ref:
            errors.append("Missing asset reference")
        else:
            resolved_asset_id = asset_ref_to_id.get(row.asset_ref)
            if resolved_asset_id is None:
                errors.append(f"Cannot resolve asset: '{row.asset_ref}'")

        # Tag
        resolved_tag_id: int | None = None
        if not row.tag_ref:
            errors.append("Missing tag reference")
        else:
            resolved_tag_id = tag_name_to_id.get(row.tag_ref.lower())
            if resolved_tag_id is None:
                # Try numeric
                if row.tag_ref.isdigit():
                    resolved_tag_id = int(row.tag_ref)
                else:
                    errors.append(f"Cannot resolve tag: '{row.tag_ref}'")

        # Value
        if row.value is None:
            errors.append("Missing value")
        else:
            import math
            if math.isnan(row.value) or math.isinf(row.value):
                errors.append("Value is not a finite number")

        if errors:
            row.status = "invalid"
            row.error_message = "; ".join(errors)
            continue

        # Store resolved IDs
        row.asset_id = resolved_asset_id
        row.tag_def_id = resolved_tag_id

        # Duplicate detection
        existing = (
            db.query(RawData)
            .filter(
                RawData.ts == row.ts,
                RawData.asset_id == resolved_asset_id,
                RawData.tag_def_id == resolved_tag_id,
            )
            .first()
        )

        if existing and existing.value == row.value:
            row.status = "duplicate"
            row.error_message = "Exact duplicate – same value already exists"
        elif existing:
            row.status = "updated"   # will overwrite existing value
        else:
            row.status = "valid"     # new row

    db.commit()
    return _build_validate_response(db, batch_id)


def _build_validate_response(db: Session, batch_id: uuid.UUID) -> ValidateResponse:
    rows = db.query(UploadStaging).filter(UploadStaging.batch_id == batch_id).all()
    counts: dict[str, int] = {"valid": 0, "invalid": 0, "duplicate": 0, "updated": 0}
    for r in rows:
        if r.status in counts:
            counts[r.status] += 1
    return ValidateResponse(
        batch_id=str(batch_id),
        valid_count=counts["valid"],
        invalid_count=counts["invalid"],
        duplicate_count=counts["duplicate"],
        new_count=counts["valid"],
        updated_count=counts["updated"],
    )


# ---------------------------------------------------------------------------
# Step 3: Diff preview
# ---------------------------------------------------------------------------

def get_diff(db: Session, batch_id: uuid.UUID) -> DiffResponse:
    """Return staging rows grouped by status."""

    rows = (
        db.query(UploadStaging)
        .filter(UploadStaging.batch_id == batch_id)
        .order_by(UploadStaging.row_number)
        .all()
    )

    grouped: dict[str, list[StagingRowOut]] = {
        "new": [],
        "updated": [],
        "duplicate": [],
        "invalid": [],
    }

    for r in rows:
        out = StagingRowOut.model_validate(r)
        if r.status == "valid":
            grouped["new"].append(out)
        elif r.status == "updated":
            grouped["updated"].append(out)
        elif r.status == "duplicate":
            grouped["duplicate"].append(out)
        elif r.status == "invalid":
            grouped["invalid"].append(out)

    return DiffResponse(
        batch_id=str(batch_id),
        **grouped,
    )


# ---------------------------------------------------------------------------
# Step 4: Apply batch
# ---------------------------------------------------------------------------

def apply_batch(
    db: Session,
    batch_id: uuid.UUID,
    user_email: str = "system",
) -> ApplyResponse:
    """UPSERT all valid/updated staging rows into raw_data and write edit log.

    Idempotent: re-applying a done batch returns the same counts without
    re-inserting.
    """
    # Check if already applied
    sample = db.query(UploadStaging).filter(UploadStaging.batch_id == batch_id).first()
    if sample is None:
        raise ValueError(f"Batch {batch_id} not found")

    # Only apply rows that are valid or updated (not duplicate/invalid/done)
    applyable_statuses = ("valid", "updated")
    rows = (
        db.query(UploadStaging)
        .filter(
            UploadStaging.batch_id == batch_id,
            UploadStaging.status.in_(applyable_statuses),
        )
        .all()
    )

    applied = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        if row.ts is None or row.asset_id is None or row.tag_def_id is None:
            row.status = "invalid"
            row.error_message = "Missing required fields after validation"
            skipped += 1
            continue

        existing: RawData | None = (
            db.query(RawData)
            .filter(
                RawData.ts == row.ts,
                RawData.asset_id == row.asset_id,
                RawData.tag_def_id == row.tag_def_id,
            )
            .first()
        )

        old_value: float | None = None

        if existing:
            old_value = existing.value
            existing.value = row.value
        else:
            db.add(
                RawData(
                    ts=row.ts,
                    asset_id=row.asset_id,
                    tag_def_id=row.tag_def_id,
                    tag_def_name=row.tag_ref,  # preserve name if available
                    value=row.value,
                )
            )

        # Edit log
        db.add(
            TimeseriesEditLog(
                ts=row.ts,
                asset_id=row.asset_id,
                tag_def_id=row.tag_def_id,
                old_value=old_value,
                new_value=row.value,
                updated_by=user_email,
                updated_at=now,
                source="upload",
            )
        )

        # Mark staging row as done
        row.status = _BATCH_DONE_STATUS
        applied += 1

    db.commit()

    return ApplyResponse(
        batch_id=str(batch_id),
        applied=applied,
        skipped=skipped,
    )
